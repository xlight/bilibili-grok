"""BiliBili @mention monitor."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass

import httpx

from grok.db import Database, Mention

logger = logging.getLogger(__name__)


@dataclass
class MentionItem:
    """Raw mention item from API - preserves complete data structure."""

    raw: dict

    @property
    def id(self) -> int:
        return self.raw.get("id", 0)

    @property
    def type(self) -> str:
        return self.raw.get("item", {}).get("type", "reply")

    @property
    def oid(self) -> int:
        return self.raw.get("item", {}).get("subject_id", 0)

    @property
    def root(self) -> int:
        return self.raw.get("item", {}).get("root_id", 0)

    @property
    def parent(self) -> int:
        return self.raw.get("item", {}).get("target_id", 0)

    @property
    def mid(self) -> int:
        return self.raw.get("user", {}).get("mid", 0)

    @property
    def uname(self) -> str:
        return self.raw.get("user", {}).get("nickname", "")

    @property
    def content(self) -> str:
        return self.raw.get("item", {}).get("source_content", "")

    @property
    def ctime(self) -> int:
        return self.raw.get("at_time", 0)

    @property
    def hide_reply_button(self) -> bool:
        return self.raw.get("item", {}).get("hide_reply_button", False)


class MentionMonitor:
    """Monitor BiliBili @mentions."""

    API_URL = "https://api.bilibili.com"

    def __init__(
        self,
        cookies: dict,
        db: Database,
        poll_interval: int = 60,
        batch_size: int = 20,
    ):
        self.cookies = cookies
        self.db = db
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self._running = False
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.bilibili.com",
                },
                cookies=self.cookies,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_unread_count(self) -> int:
        """Get unread mention count."""
        logger.info("Fetching unread mention count...")
        resp = await self.client.get(f"{self.API_URL}/x/msgfeed/at")
        resp.raise_for_status()
        data = resp.json()

        if data["code"] != 0:
            raise Exception(f"Failed to fetch unread count: {data.get('message')}")

        count = data["data"].get("unread_at", 0)
        logger.info(f"Unread mention count: {count}")
        return count

    async def fetch_mention_list(
        self, cursor: int = 0, size: int = 20
    ) -> tuple[list[MentionItem], int]:
        """Fetch mention list with pagination.

        Returns:
            tuple: (list of MentionItem, next cursor)
        """
        logger.info(f"Fetching mention list (cursor: {cursor}, size: {size})")
        resp = await self.client.get(
            f"{self.API_URL}/x/msgfeed/at",
            params={"type": "at", "cursor": cursor, "size": size},
        )
        resp.raise_for_status()
        data = resp.json()

        if data["code"] != 0:
            raise Exception(f"Failed to fetch mentions: {data.get('message')}")

        items = data["data"].get("items", [])
        mentions = [self._parse_mention_item(item) for item in items]

        next_cursor = data["data"].get("cursor", {}).get("cursor", 0)

        return mentions, next_cursor

    def _parse_mention_item(self, item: dict) -> MentionItem:
        """Parse mention item from API response - preserves raw structure."""
        return MentionItem(raw=item)

    async def filter_valid_mentions(self, mentions: list[MentionItem]) -> list[MentionItem]:
        """Filter mentions that can be replied to."""
        valid = []
        valid_types = {1, 2, 17, "reply", "dynamic"}

        for mention in mentions:
            if mention.hide_reply_button:
                logger.info(f"Mention {mention.id} skipped: hide_reply_button=True")
                continue

            type_val = mention.type
            if isinstance(type_val, str):
                type_val = type_val.lower()

            if type_val not in valid_types:
                logger.info(f"Mention {mention.id} skipped: type {mention.type} not in valid types")
                continue
            valid.append(mention)

        if valid:
            logger.info(f"Found {len(valid)} valid mentions to process")
        return valid

    async def sync_mentions(self) -> int:
        """Sync mentions from API to database."""
        cursor = 0
        total_synced = 0
        total_fetched = 0

        logger.info("Starting mention sync...")

        while True:
            if not self._running:
                logger.info("Mention monitor stopped, aborting sync")
                break

            mentions, cursor = await self.fetch_mention_list(cursor, self.batch_size)

            if not mentions:
                logger.info("No more mentions to fetch")
                break

            total_fetched += len(mentions)
            logger.info(f"Fetched {len(mentions)} mentions (cursor: {cursor})")
            # logger.info(f"Fetched mentions: {mentions}")

            valid_mentions = await self.filter_valid_mentions(mentions)
            logger.info(f"Filtered to {len(valid_mentions)} valid mentions")

            for mention in valid_mentions:
                db_mention = Mention(
                    id=mention.id,
                    type=mention.type,
                    oid=mention.oid,
                    root=mention.root,
                    parent=mention.parent,
                    mid=mention.mid,
                    uname=mention.uname,
                    content=mention.content,
                    ctime=mention.ctime,
                    status="pending",
                )
                inserted = await self.db.insert_mention(db_mention)
                if inserted:
                    total_synced += 1
                    logger.info(f"Inserted new mention {mention.id} from {mention.uname}")
                    logger.info(f"Full mention JSON: {mention}")

            if cursor == 0:
                break

        logger.info(f"Mention sync complete: {total_synced} new, {total_fetched} total fetched")
        return total_synced

    async def process_mentions(self, handler: Callable[[Mention], None]) -> None:
        """Process pending mentions with handler callback."""
        if not self._running:
            logger.info("Mention monitor stopped, skipping processing")
            return

        pending = await self.db.get_pending_mentions(self.batch_size)

        if not pending:
            logger.info("No pending mentions to process")
            return

        logger.info(f"Processing {len(pending)} pending mentions")

        for mention in pending:
            if not self._running:
                logger.info("Mention monitor stopped during processing")
                break

            logger.info(
                f"Processing mention {mention.id} from {mention.uname}: {mention.content[:50]}..."
            )
            await self.db.update_mention_status(mention.id, "processing")

            try:
                reply_content = await handler(mention)

                if not self._running:
                    logger.info("Mention monitor stopped, saving state and exiting")
                    break

                if reply_content:
                    await self.db.update_mention_status(mention.id, "replied", reply_content)
                    logger.info(f"Replied to mention {mention.id}: {reply_content[:50]}...")
                else:
                    await self.db.update_mention_status(mention.id, "skipped")
                    logger.info(f"Skipped mention {mention.id}")
            except Exception as e:
                await self.db.update_mention_status(mention.id, "failed")
                logger.error(f"Failed to process mention {mention.id}: {e}")

    async def run(self, handler):
        """Run the mention monitor loop."""
        self._running = True
        logger.info("Mention monitor started")

        while self._running:
            try:
                logger.info(f"Poll interval: {self.poll_interval}s")
                await self.sync_mentions()
                await self.process_mentions(handler)
            except asyncio.CancelledError:
                logger.info("Mention monitor cancelled, shutting down...")
                self._running = False
                break
            except Exception as e:
                logger.error(f"Error in mention monitor: {e}")

            for _ in range(self.poll_interval):
                if not self._running:
                    break
                await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the monitor."""
        logger.info("Stopping mention monitor...")
        self._running = False
