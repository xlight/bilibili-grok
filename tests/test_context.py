"""Tests for context module."""

from unittest.mock import AsyncMock

import pytest

from grok.context import CommentContext, ContextFetcher, VideoContext


@pytest.fixture
def context_fetcher(mock_cookie_dict, mock_credentials):
    """Create a ContextFetcher instance."""
    return ContextFetcher(cookies=mock_cookie_dict, credentials=mock_credentials)


@pytest.mark.asyncio
class TestContextFetcher:
    async def test_fetch_video_info_success(self, context_fetcher, mock_httpx_response):
        mock_response = mock_httpx_response(
            {
                "code": 0,
                "data": {
                    "title": "测试视频标题",
                    "desc": "测试视频简介",
                },
            }
        )
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(return_value=mock_response)

        result = await context_fetcher.fetch_video_info(123456)

        assert result is not None
        assert result.title == "测试视频标题"
        assert result.description == "测试视频简介"

    async def test_fetch_video_info_api_error(self, context_fetcher, mock_httpx_response):
        mock_response = mock_httpx_response({"code": -400, "message": "请求错误"})
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(return_value=mock_response)

        result = await context_fetcher.fetch_video_info(123456)

        assert result is None

    async def test_fetch_video_info_http_error(self, context_fetcher):
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(side_effect=Exception("Network error"))

        result = await context_fetcher.fetch_video_info(123456)

        assert result is None

    async def test_fetch_target_comment_root_id_zero(self, context_fetcher, mock_httpx_response):
        mock_response = mock_httpx_response(
            {
                "code": 0,
                "data": {
                    "replies": [
                        {
                            "rpid": 123456,
                            "content": {"message": "根评论内容"},
                            "member": {"uname": "评论者"},
                        }
                    ]
                },
            }
        )
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(return_value=mock_response)

        result = await context_fetcher.fetch_target_comment(
            subject_id=987654, target_id=123456, root_id=0
        )

        assert result is not None
        assert result.content == "根评论内容"
        assert result.user_nickname == "评论者"

    async def test_fetch_target_comment_with_root_id(self, context_fetcher, mock_httpx_response):
        mock_response = mock_httpx_response(
            {
                "code": 0,
                "data": {
                    "replies": [
                        {
                            "rpid": 123456,
                            "rpid_str": "123456",
                            "content": {"message": "目标评论内容"},
                            "member": {"uname": "回复者"},
                        }
                    ]
                },
            }
        )
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(return_value=mock_response)

        result = await context_fetcher.fetch_target_comment(
            subject_id=987654, target_id=123456, root_id=111111
        )

        assert result is not None
        assert result.content == "目标评论内容"

    async def test_fetch_target_comment_not_found(self, context_fetcher, mock_httpx_response):
        mock_response = mock_httpx_response(
            {
                "code": 0,
                "data": {
                    "replies": [
                        {
                            "rpid": 999999,
                            "content": {"message": "其他评论"},
                            "member": {"uname": "其他人"},
                        }
                    ]
                },
            }
        )
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(return_value=mock_response)

        result = await context_fetcher.fetch_target_comment(
            subject_id=987654, target_id=123456, root_id=111111
        )

        assert result is None

    async def test_fetch_target_comment_api_error(self, context_fetcher, mock_httpx_response):
        mock_response = mock_httpx_response({"code": -400, "message": "请求错误"})
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(return_value=mock_response)

        result = await context_fetcher.fetch_target_comment(
            subject_id=987654, target_id=123456, root_id=0
        )

        assert result is None

    async def test_fetch_target_comment_empty_replies(self, context_fetcher, mock_httpx_response):
        mock_response = mock_httpx_response({"code": 0, "data": {"replies": []}})
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(return_value=mock_response)

        result = await context_fetcher.fetch_target_comment(
            subject_id=987654, target_id=123456, root_id=0
        )

        assert result is None

    async def test_fetch_root_comment_success(self, context_fetcher, mock_httpx_response):
        mock_response = mock_httpx_response(
            {
                "code": 0,
                "data": {
                    "replies": [
                        {
                            "rpid": 111111,
                            "content": {"message": "根评论内容"},
                            "member": {"uname": "根评论者"},
                        }
                    ]
                },
            }
        )
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(return_value=mock_response)

        result = await context_fetcher.fetch_root_comment(subject_id=987654, root_id=111111)

        assert result is not None
        assert result.content == "根评论内容"
        assert result.user_nickname == "根评论者"

    async def test_fetch_root_comment_api_error(self, context_fetcher, mock_httpx_response):
        mock_response = mock_httpx_response({"code": -400, "message": "请求错误"})
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(return_value=mock_response)

        result = await context_fetcher.fetch_root_comment(subject_id=987654, root_id=111111)

        assert result is None

    async def test_fetch_root_comment_http_error(self, context_fetcher):
        context_fetcher._client = AsyncMock()
        context_fetcher._client.get = AsyncMock(side_effect=Exception("Network error"))

        result = await context_fetcher.fetch_root_comment(subject_id=987654, root_id=111111)

        assert result is None

    async def test_client_lazy_initialization(self, context_fetcher):
        assert context_fetcher._client is None

        client = context_fetcher.client
        assert client is not None

        assert context_fetcher._client is client

    async def test_close(self, context_fetcher):
        mock_client = AsyncMock()
        context_fetcher._client = mock_client

        await context_fetcher.close()

        mock_client.aclose.assert_called_once()
        assert context_fetcher._client is None

    async def test_close_no_client(self, context_fetcher):
        context_fetcher._client = None
        await context_fetcher.close()
        assert context_fetcher._client is None


class TestVideoContext:
    def test_video_context_creation(self):
        context = VideoContext(title="测试标题", description="测试简介")
        assert context.title == "测试标题"
        assert context.description == "测试简介"

    def test_video_context_default_description(self):
        context = VideoContext(title="测试标题")
        assert context.title == "测试标题"
        assert context.description == ""


class TestCommentContext:
    def test_comment_context_creation(self):
        context = CommentContext(content="评论内容", user_nickname="用户名")
        assert context.content == "评论内容"
        assert context.user_nickname == "用户名"

    def test_comment_context_default_nickname(self):
        context = CommentContext(content="评论内容")
        assert context.content == "评论内容"
        assert context.user_nickname == ""
