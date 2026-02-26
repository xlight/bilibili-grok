"""Tests for reply module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from grok.reply import CommentDeletedError, CommentReply, RateLimitError, ReplyError


@pytest.fixture
def reply(mock_cookie_dict):
    """Create a CommentReply instance."""
    return CommentReply(cookies=mock_cookie_dict, rate_limit_seconds=0.1)


class TestCommentReplySync:
    def test_get_type_name(self, reply):
        assert reply._get_type_name(1) == "reply"
        assert reply._get_type_name(2) == "like"
        assert reply._get_type_name(4) == "share"
        assert reply._get_type_name("reply") == "reply"
        assert reply._get_type_name("dynamic") == "reply"
        assert reply._get_type_name(999) == "reply"

    def test_get_type_id(self, reply):
        assert reply._get_type_id(1) == 1
        assert reply._get_type_id(2) == 2
        assert reply._get_type_id("reply") == 1
        assert reply._get_type_id("like") == 2
        assert reply._get_type_id("dynamic") == 1
        assert reply._get_type_id("unknown") == 1


@pytest.mark.asyncio
class TestCommentReplyAsync:
    async def test_close(self, reply):
        await reply.close()
        assert reply._client is None

    async def test_reply_to_comment_success(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": 0, "data": {"rpid": 12345}})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        result = await reply.reply_to_comment(
            oid=987654, type_=1, message="测试回复", root=0, parent=0
        )

        assert result == {"rpid": 12345}

    async def test_reply_to_comment_not_logged_in(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": -101, "message": "未登录"})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(ReplyError, match="Not logged in"):
            await reply.reply_to_comment(oid=987654, type_=1, message="测试回复")

    async def test_reply_to_comment_account_disabled(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": -102, "message": "账号封禁"})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(ReplyError, match="Account disabled"):
            await reply.reply_to_comment(oid=987654, type_=1, message="测试回复")

    async def test_reply_to_comment_rate_limited(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": -104, "message": "请求过于频繁"})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(RateLimitError):
            await reply.reply_to_comment(oid=987654, type_=1, message="测试回复")

    async def test_reply_to_comment_request_blocked(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": -412, "message": "请求被拦截"})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(ReplyError, match="Request blocked"):
            await reply.reply_to_comment(oid=987654, type_=1, message="测试回复")

    async def test_reply_to_comment_deleted(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": 12002, "message": "评论已删除"})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(CommentDeletedError):
            await reply.reply_to_comment(oid=987654, type_=1, message="测试回复")

    async def test_reply_to_comment_cannot_reply(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": 12030, "message": "无法回复"})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(ReplyError, match="Cannot reply"):
            await reply.reply_to_comment(oid=987654, type_=1, message="测试回复")

    async def test_reply_to_comment_unknown_error(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": -999, "message": "未知错误"})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        with pytest.raises(ReplyError, match="Failed to reply"):
            await reply.reply_to_comment(oid=987654, type_=1, message="测试回复")

    async def test_rate_limit(self, mock_cookie_dict):
        reply = CommentReply(cookies=mock_cookie_dict, rate_limit_seconds=0.2)
        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0, "data": {}}
        mock_response.raise_for_status = MagicMock()
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        start = asyncio.get_event_loop().time()
        await reply.reply_to_comment(oid=1, type_=1, message="first")
        await reply.reply_to_comment(oid=2, type_=1, message="second")
        elapsed = asyncio.get_event_loop().time() - start

        assert elapsed >= 0.2

    async def test_reply_to_mention(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": 0, "data": {"rpid": 12345}})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        result = await reply.reply_to_mention(
            oid=987654, type_="reply", message="测试回复", root=100, parent=200
        )

        assert result == {"rpid": 12345}
        call_args = reply._client.post.call_args
        assert call_args[1]["data"]["oid"] == 987654
        assert call_args[1]["data"]["root"] == 100
        assert call_args[1]["data"]["parent"] == 200

    async def test_reply_to_reply(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": 0, "data": {"rpid": 12345}})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        result = await reply.reply_to_reply(
            oid=987654,
            type_=1,
            message="测试回复",
            root=100,
            parent=200,
            reply_mid=123456,
        )

        assert result == {"rpid": 12345}
        call_args = reply._client.post.call_args
        assert call_args[1]["data"]["at_mids"] == "123456"

    async def test_reply_to_reply_without_mid(self, reply, mock_httpx_response):
        mock_response = mock_httpx_response({"code": 0, "data": {"rpid": 12345}})
        reply._client = AsyncMock()
        reply._client.post = AsyncMock(return_value=mock_response)

        result = await reply.reply_to_reply(
            oid=987654, type_=1, message="测试回复", root=100, parent=200
        )

        assert result == {"rpid": 12345}
        call_args = reply._client.post.call_args
        assert "at_mids" not in call_args[1]["data"]
