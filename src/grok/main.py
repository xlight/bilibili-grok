"""Main entry point for Bilibili Grok bot."""

import asyncio
import logging

# logging.getLogger("langgraph").setLevel(logging.DEBUG)
# logging.getLogger("langgraph.graph").setLevel(logging.DEBUG)
# logging.getLogger("langchain").setLevel(logging.DEBUG)
# logging.getLogger("langchain_core").setLevel(logging.DEBUG)
# logging.getLogger("langchain_openai").setLevel(logging.DEBUG)
# logging.getLogger("litellm").setLevel(logging.DEBUG)
# logging.getLogger("litellm.main").setLevel(logging.DEBUG)
# logging.getLogger("httpx").setLevel(logging.INFO)
from grok import __version__
from grok.agent import AgentConfig, BilibiliAgent
from grok.config import Config, ConfigError, load_config, validate_config
from grok.context import ContextFetcher
from grok.db import Database, Mention
from grok.health import GracefulShutdown, HealthCheck
from grok.logger import get_logger, setup_logging
from grok.login import BilibiliLogin
from grok.mention import MentionMonitor, strip_bot_mentions
from grok.reply import CommentReply

logger = get_logger(__name__)


class GrokBot:
    """Main bot class."""

    def __init__(self, config: Config):
        self.config = config
        self._login: BilibiliLogin | None = None
        self._db: Database | None = None
        self._mention_monitor: MentionMonitor | None = None
        self._reply: CommentReply | None = None
        self._agent: BilibiliAgent | None = None
        self._health: HealthCheck | None = None
        self._shutdown: GracefulShutdown | None = None
        self._context_fetcher: ContextFetcher | None = None
        self._bot_mid: int = 0
        self._bot_nickname: str = ""
        self._shutdown_started: bool = False

    async def initialize(self) -> None:
        """Initialize all components."""
        logger.info("Initializing Grok bot...")

        self._login = BilibiliLogin(
            credential_path=self.config.bilibili.credential_path,
        )

        credentials = await self._login.ensure_valid_credentials()
        logger.info(f"Logged in as user: {credentials.dedeuserid}")

        self._db = Database(db_path="data/grok.db")
        await self._db.connect()
        logger.info("Database initialized")

        self._reply = CommentReply(
            cookies=self._login.get_cookie_dict(),
            rate_limit_seconds=self.config.reply.rate_limit_seconds,
        )

        self._agent = BilibiliAgent(
            config=AgentConfig(
                model=self.config.agent.model,
                api_base=self.config.agent.api_base,
                api_key=self.config.agent.api_key,
                max_tokens=self.config.agent.max_tokens,
                temperature=self.config.agent.temperature,
                system_prompt=self.config.agent.system_prompt,
            ),
        )

        self._context_fetcher = ContextFetcher(
            cookies=self._login.get_cookie_dict(),
            credentials=credentials,
        )
        logger.info("Context fetcher initialized")
        self._bot_mid = int(credentials.dedeuserid)

        # Get bot's nickname for mention stripping
        self._bot_nickname = await self._login.get_user_name() or ""
        logger.info(f"Bot mid: {self._bot_mid}, nickname: {self._bot_nickname}")

        self._mention_monitor = MentionMonitor(
            cookies=self._login.get_cookie_dict(),
            db=self._db,
            poll_interval=self.config.monitor.poll_interval,
            batch_size=self.config.monitor.batch_size,
        )

        if self.config.health.enabled:
            self._health = HealthCheck(
                host=self.config.health.host,
                port=self.config.health.port,
            )
            self._health.register_component("database", self._check_database)
            self._health.register_component("credential", self._check_credential)
            await self._health.start()
            logger.info(
                f"Health check server started on {self.config.health.host}:{self.config.health.port}"
            )

        self._shutdown = GracefulShutdown()
        self._shutdown.register_callback(self.shutdown)
        self._shutdown.setup()

        logger.info("Grok bot initialized successfully")

    async def _check_database(self) -> dict:
        """Check database health."""
        try:
            stats = await self._db.get_stats()
            return {
                "status": "healthy",
                "stats": stats,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }

    async def _check_credential(self) -> dict:
        """Check credential health."""
        if not self._login.credentials:
            return {"status": "unhealthy", "error": "No credentials"}

        if self._login.credentials.is_expired:
            return {"status": "unhealthy", "error": "Credentials expired"}

        return {"status": "healthy"}

    async def _handle_mention(self, mention: Mention) -> str | None:
        """Handle a mention - generate and send reply."""
        logger.info(f"Processing mention {mention.id} from {mention.uname}")

        try:
            # Fetch context (video info, root/target comments)
            context = {}

            if self._context_fetcher:
                logger.info(f"Fetching context for mention {mention.id}")

                # Fetch video info
                if mention.oid:
                    video_info = await self._context_fetcher.fetch_video_info(mention.oid)
                    if video_info:
                        logger.info(f"Video info: {video_info}")
                        context["video_title"] = video_info.title[:1000]
                        # Add description if available
                        if video_info.description:
                            context["video_description"] = video_info.description[:500]
                    else:
                        logger.warning(f"Failed to fetch video info for oid={mention.oid}")

                # Fetch target comment (the comment being replied to)
                if mention.parent and mention.oid:
                    target_info = await self._context_fetcher.fetch_target_comment(
                        mention.oid, mention.parent, mention.root
                    )
                    if target_info:
                        logger.info(f"Target comment: {target_info}")
                        context["target_content"] = target_info.content[:2000]

                # Fetch root comment (top-level comment)
                if mention.root and mention.oid and mention.root != mention.parent:
                    root_info = await self._context_fetcher.fetch_root_comment(
                        mention.oid, mention.root
                    )
                    if root_info:
                        logger.info(f"Root comment: {root_info.content[:50]}...")
                        context["root_content"] = root_info.content[:2000]

                logger.info(f"Context collected: {list(context.keys()) if context else 'none'}")
            else:
                logger.warning("Context fetcher not initialized")

            # Clean mention content
            # 1. Strip "回复 @username :" prefix if this is a reply to specific comment
            cleaned_content = mention.content
            if mention.parent and mention.parent != 0:
                # Pattern: "回复 @username :content" or "回复 @username:content"
                import re

                reply_pattern = r"^回复\s+@\S+\s*:\s*"
                cleaned_content = re.sub(reply_pattern, "", cleaned_content)
                logger.info(f"Removed reply prefix, cleaned: {cleaned_content[:50]}...")

            # 2. Strip bot mentions using at_details if available
            at_details = (
                mention.at_details if hasattr(mention, "at_details") and mention.at_details else []
            )
            cleaned_content = strip_bot_mentions(
                cleaned_content,
                at_details=at_details,
                bot_mid=self._bot_mid,
                bot_nickname=self._bot_nickname,
            )

            # Additionally remove any remaining @username patterns to clean up
            import re

            cleaned_content = re.sub(r"@\S+\s*", "", cleaned_content).strip()

            logger.info(f"Final cleaned content: {cleaned_content[:50]}...")

            logger.info(f"Calling LLM with context: {list(context.keys()) if context else 'none'}")
            reply_content = await self._agent.generate_reply(
                mention_content=cleaned_content,
                username=mention.uname,
                context=context if context else None,
            )

            logger.info(f"Generated reply: {reply_content}")

            await self._reply.reply_to_mention(
                oid=mention.oid,
                type_=mention.type,
                message=reply_content,
                root=mention.root,
                parent=mention.parent,
            )

            logger.info(f"Successfully replied to mention {mention.id}")
            return reply_content

        except Exception as e:
            logger.error(f"Failed to handle mention {mention.id}: {e}")
            return None

    async def run(self):
        """Run the bot."""
        logger.info("Starting Grok bot...")

        await self._mention_monitor.run(self._handle_mention)

    async def shutdown(self) -> None:
        """Shutdown all components."""

        if self._shutdown_started:
            logger.info("Shutdown already in progress")
            return

        self._shutdown_started = True
        logger.info("Shutting down Grok bot...")

        current_task = asyncio.current_task()
        if current_task:
            current_task.cancel()

        if self._mention_monitor:
            await self._mention_monitor.stop()

        if self._health:
            await self._health.stop()

        if self._reply:
            await self._reply.close()

        if self._context_fetcher:
            await self._context_fetcher.close()

        if self._db:
            await self._db.close()

        if self._login:
            await self._login.close()

        if self._shutdown:
            self._shutdown.cleanup()

        logger.info("Grok bot shutdown complete")


async def main() -> int:
    """Main entry point."""
    try:
        config = load_config("config.yaml")
        validate_config(config)
    except ConfigError as e:
        print(f"Configuration error: {e}")
        return 1

    debug_loggers = [
        # "langgraph",
        # "langgraph.graph",
        # "langchain",
        # "langchain_core",
        # "litellm",
        # "litellm.main",
    ]
    for name in debug_loggers:
        logging.getLogger(name).setLevel(logging.DEBUG)

    setup_logging(
        level=config.logging.level,
        format_=config.logging.format,
        log_file=config.logging.file,
        max_bytes=config.logging.max_bytes,
        backup_count=config.logging.backup_count,
    )

    logger.info(f"Starting Bilibili Grok v{__version__}")

    bot = GrokBot(config)

    try:
        await bot.initialize()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await bot.shutdown()

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
