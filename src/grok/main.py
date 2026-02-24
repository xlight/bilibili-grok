"""Main entry point for Bilibili Grok bot."""

import asyncio
import signal
from typing import Optional

from grok import __version__
from grok.agent import BilibiliAgent, AgentConfig
from grok.config import Config, ConfigError, load_config, validate_config
from grok.db import Database
from grok.health import GracefulShutdown, HealthCheck
from grok.login import BilibiliLogin
from grok.logger import get_logger, setup_logging
from grok.mention import MentionMonitor
from grok.reply import CommentReply


logger = get_logger(__name__)


class GrokBot:
    """Main bot class."""

    def __init__(self, config: Config):
        self.config = config
        self._login: Optional[BilibiliLogin] = None
        self._db: Optional[Database] = None
        self._mention_monitor: Optional[MentionMonitor] = None
        self._reply: Optional[CommentReply] = None
        self._agent: Optional[BilibiliAgent] = None
        self._health: Optional[HealthCheck] = None
        self._shutdown: Optional[GracefulShutdown] = None

    async def initialize(self):
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

    async def _handle_mention(self, mention) -> Optional[str]:
        """Handle a mention - generate and send reply."""
        logger.info(f"Processing mention {mention.id} from {mention.uname}")

        try:
            reply_content = await self._agent.generate_reply(
                mention_content=mention.content,
                username=mention.uname,
            )

            logger.info(f"Generated reply: {reply_content}")

            await self._reply.reply_to_mention(
                oid=mention.oid,
                type_=mention.type,
                message=reply_content,
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

    async def shutdown(self):
        """Shutdown all components."""
        logger.info("Shutting down Grok bot...")

        if self._mention_monitor:
            await self._mention_monitor.stop()

        if self._health:
            await self._health.stop()

        if self._reply:
            await self._reply.close()

        if self._db:
            await self._db.close()

        if self._login:
            await self._login.close()

        if self._shutdown:
            self._shutdown.cleanup()

        logger.info("Grok bot shutdown complete")


async def main():
    """Main entry point."""
    try:
        config = load_config("config.yaml")
        validate_config(config)
    except ConfigError as e:
        print(f"Configuration error: {e}")
        return 1

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
