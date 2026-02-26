"""Context fetching for Bilibili video and comments."""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from grok.login import Credentials

logger = logging.getLogger(__name__)


@dataclass
class VideoContext:
    """Video metadata."""

    title: str
    description: str = ""


@dataclass
class CommentContext:
    """Comment content."""

    content: str
    user_nickname: str = ""


class ContextFetcher:
    """Fetch context from Bilibili API."""

    API_URL = "https://api.bilibili.com"

    def __init__(self, cookies: dict[str, str], credentials: Credentials):
        self.cookies = cookies
        self.credentials = credentials
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
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
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def fetch_video_info(self, subject_id: int) -> Optional[VideoContext]:
        """Fetch video metadata by subject_id.

        Args:
            subject_id: Video ID from mention data

        Returns:
            VideoContext with title and description, or None if failed
        """
        try:
            logger.debug(f"Fetching video info for subject_id={subject_id}")
            # Try with aid (av number) first
            resp = await self.client.get(
                f"{self.API_URL}/x/web-interface/view",
                params={"aid": subject_id},
            )
            resp.raise_for_status()
            data = resp.json()

            if data["code"] != 0:
                # Try with bvid if aid fails
                logger.debug(f"Video info with aid failed, trying bvid: {data.get('message')}")
                return None

            video_data = data["data"]
            return VideoContext(
                title=video_data.get("title", ""),
                description=video_data.get("desc", ""),
            )

        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch video info: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error fetching video info: {e}")
            return None

    async def fetch_target_comment(
        self, subject_id: int, target_id: int, root_id: int = 0
    ) -> Optional[CommentContext]:
        """Fetch target comment content using reply tree API.

        Args:
            subject_id: Video ID (oid)
            target_id: Comment ID (parent)
            root_id: Root comment ID (optional, for nested replies)

        Returns:
            CommentContext with content, or None if failed
        """
        try:
            # When root_id is 0, target_id IS the root comment
            # Use /x/v2/reply API instead of /x/v2/reply/reply
            if root_id == 0:
                logger.info(
                    f"Fetching root comment as target: oid={subject_id}, target={target_id}"
                )
                resp = await self.client.get(
                    f"{self.API_URL}/x/v2/reply",
                    params={
                        "oid": subject_id,
                        "type": 1,
                        "root": target_id,
                        "ps": 1,
                        "pn": 1,
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                if data["code"] != 0:
                    logger.warning(
                        f"Comment API returned error: {data.get('message')}, code={data.get('code')}"
                    )
                    return None

                replies = data.get("data", {}).get("replies", [])
                if not replies:
                    logger.warning(f"No comment found for root={target_id}")
                    return None

                comment_data = replies[0]
                content = comment_data.get("content", {}).get("message", "")
                member = comment_data.get("member", {})
                nickname = member.get("uname", "")
                logger.info(f"Found root-as-target comment: {content[:50]}...")
                return CommentContext(content=content, user_nickname=nickname)

            # Normal case: fetch from reply tree
            logger.info(
                f"Fetching target comment: oid={subject_id}, target={target_id}, root={root_id}"
            )
            resp = await self.client.get(
                f"{self.API_URL}/x/v2/reply/reply",
                params={
                    "oid": subject_id,
                    "type": 1,  # 1 = video comment
                    "root": root_id,
                    "ps": 20,  # get more replies to find target
                    "pn": 1,  # page number
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if data["code"] != 0:
                logger.warning(
                    f"Comment API returned error: {data.get('message')}, code={data.get('code')}"
                )
                return None

            # Search for the target comment in replies list
            replies = data.get("data", {}).get("replies", [])
            logger.info(f"Found {len(replies)} replies in response")

            for reply in replies:
                rpid = reply.get("rpid")
                rpid_str = reply.get("rpid_str")
                # Match either numeric or string ID
                if rpid == target_id or rpid_str == str(target_id):
                    content = reply.get("content", {}).get("message", "")
                    member = reply.get("member", {})
                    nickname = member.get("uname", "")
                    logger.info(f"Found target comment: {content[:50]}...")
                    return CommentContext(content=content, user_nickname=nickname)

            # If not found in first page, log and return None
            logger.warning(f"Target comment {target_id} not found in {len(replies)} replies")
            # Log the IDs we found for debugging
            found_ids = [r.get("rpid") for r in replies[:5]]
            logger.info(f"Found reply IDs (first 5): {found_ids}")
            return None

        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch target comment: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error fetching target comment: {e}")
            return None

    async def fetch_root_comment(self, subject_id: int, root_id: int) -> Optional[CommentContext]:
        """Fetch root comment (顶楼) content using reply API.

        Args:
            subject_id: Video ID (oid)
            root_id: Root comment ID

        Returns:
            CommentContext with content, or None if failed
        """
        try:
            logger.debug(f"Fetching root comment: oid={subject_id}, root={root_id}")
            # Use reply API with root parameter - returns the root comment in data
            resp = await self.client.get(
                f"{self.API_URL}/x/v2/reply",
                params={
                    "oid": subject_id,
                    "type": 1,
                    "root": root_id,
                    "ps": 1,
                    "pn": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()

            if data["code"] != 0:
                logger.warning(f"Root comment API returned error: {data.get('message')}")
                return None

            # Root comment is in the first reply
            replies = data.get("data", {}).get("replies", [])
            if not replies:
                logger.debug(f"No replies found for root {root_id}")
                return None

            comment_data = replies[0]
            content = comment_data.get("content", {}).get("message", "")
            user = comment_data.get("member", {})
            nickname = user.get("uname", "")

            return CommentContext(content=content, user_nickname=nickname)

        except httpx.HTTPError as e:
            logger.warning(f"Failed to fetch root comment: {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error fetching root comment: {e}")
            return None
