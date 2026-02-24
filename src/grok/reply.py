"""BiliBili comment reply implementation."""

import asyncio
import logging
from enum import IntEnum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class ReplyType(IntEnum):
    """Reply type enum."""

    REPLY = 1
    LIKE = 2


class ReplyError(Exception):
    """Reply error."""

    pass


class CommentDeletedError(ReplyError):
    """Comment was deleted."""

    pass


class RateLimitError(ReplyError):
    """Rate limit exceeded."""

    pass


class CommentReply:
    """Handle BiliBili comment replies."""

    API_URL = "https://api.bilibili.com"

    def __init__(self, cookies: dict, rate_limit_seconds: int = 3):
        self.cookies = cookies
        self.rate_limit_seconds = rate_limit_seconds
        self._last_reply_time = 0.0
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Referer": "https://www.bilibili.com",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                cookies=self.cookies,
                timeout=30.0,
            )
        return self._client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _check_rate_limit(self):
        """Apply rate limiting between replies."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self._last_reply_time

        if time_since_last < self.rate_limit_seconds:
            await asyncio.sleep(self.rate_limit_seconds - time_since_last)

        self._last_reply_time = asyncio.get_event_loop().time()

    def _get_type_name(self, type_: int) -> str:
        """Map type ID to type name."""
        type_map = {
            1: "reply",
            2: "like",
            4: "share",
            "reply": "reply",
            "dynamic": "reply",
        }
        return type_map.get(type_, "reply")

    def _get_type_id(self, type_) -> int:
        """Map type to ID."""
        if isinstance(type_, int):
            return type_
        type_map = {
            "reply": 1,
            "like": 2,
            "dynamic": 1,
        }
        return type_map.get(str(type_), 1)

    async def reply_to_comment(
        self,
        oid: int,
        type_: int,
        message: str,
        root: int = 0,
        parent: int = 0,
        at_mids: Optional[list[int]] = None,
    ) -> dict:
        """Reply to a comment.

        Args:
            oid: Target ID (video aid or dynamic ID)
            type_: Type (1=reply, 2=like)
            message: Reply message
            root: Root comment ID for threading
            parent: Parent comment ID for threading
            at_mids: User IDs to @mention

        Returns:
            API response data

        Raises:
            CommentDeletedError: If comment was deleted
            RateLimitError: If rate limited
            ReplyError: For other errors
        """
        await self._check_rate_limit()

        type_id = self._get_type_id(type_)
        type_name = self._get_type_name(type_)

        data = {
            "message": message,
            "type": type_id,
            "oid": oid,
            "root": root,
            "parent": parent,
            "csrf": self.cookies.get("bili_jct", ""),
        }

        if at_mids:
            data["at_mids"] = ",".join(map(str, at_mids))

        logger.info(f"Sending reply to oid={oid}, type={type_id} ({type_name}): {message[:50]}...")

        resp = await self.client.post(
            f"{self.API_URL}/x/v2/{type_name}/add",
            data=data,
        )
        resp.raise_for_status()
        result = resp.json()

        logger.info(f"Reply API response: {result}")

        code = result.get("code", -1)

        if code == -101:
            raise ReplyError("Not logged in")
        if code == -102:
            raise ReplyError("Account disabled")
        if code == -104:
            raise RateLimitError("Rate limit exceeded")
        if code == -412:
            raise ReplyError("Request blocked")
        if code == 12002:
            raise CommentDeletedError("Comment was deleted")
        if code == 12030:
            raise ReplyError("Cannot reply to this comment")
        if code != 0:
            raise ReplyError(
                f"Failed to reply: code={code}, message={result.get('message', 'Unknown error')}"
            )

        return result.get("data", {})

    async def reply_to_mention(
        self, oid: int, type_: str, message: str, root: int = 0, parent: int = 0
    ) -> dict:
        """Reply to a mention (convenience method).

        For mentions, we use the root/parent IDs from the mention.
        """
        return await self.reply_to_comment(
            oid=oid,
            type_=type_,
            message=message,
            root=root,
            parent=parent,
        )

    async def reply_to_reply(
        self,
        oid: int,
        type_: int,
        message: str,
        root: int,
        parent: int,
        reply_mid: Optional[int] = None,
    ) -> dict:
        """Reply to a specific comment (threaded reply).

        Args:
            oid: Target ID
            type_: Type (1 for reply)
            message: Reply message
            root: Root comment ID
            parent: Parent comment ID (direct parent)
            reply_mid: User ID to @mention in reply
        """
        at_mids = [reply_mid] if reply_mid else None

        return await self.reply_to_comment(
            oid=oid,
            type_=type_,
            message=message,
            root=root,
            parent=parent,
            at_mids=at_mids,
        )
