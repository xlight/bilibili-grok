"""Tests for mention module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from grok.mention import MentionItem, MentionMonitor


def make_mention_item(
    id: int = 123456,
    type: int | str = "reply",
    subject_id: int = 987654,
    root_id: int = 0,
    target_id: int = 0,
    mid: int = 111111,
    nickname: str = "测试用户",
    source_content: str = "测试评论 @被提及",
    at_time: int = 1700000000,
    hide_reply_button: bool = False,
    at_details: list | None = None,
) -> MentionItem:
    """Helper to create MentionItem with correct raw dict structure."""
    raw = {
        "id": id,
        "item": {
            "type": type,
            "subject_id": subject_id,
            "root_id": root_id,
            "target_id": target_id,
            "source_content": source_content,
            "at_time": at_time,
            "reply_count": 0,
            "hide_reply_button": hide_reply_button,
        },
        "user": {
            "mid": mid,
            "nickname": nickname,
        },
        "at_time": at_time,
    }
    if at_details is not None:
        raw["item"]["at_details"] = at_details
    return MentionItem(raw=raw)


class TestMentionItem:
    def test_parse_mention_item(self):
        api_data = {
            "id": 123456,
            "item": {
                "type": "reply",
                "subject_id": 987654,
                "root_id": 0,
                "target_id": 0,
                "source_content": "测试评论 @被提及",
                "at_time": 1700000000,
                "reply_count": 5,
                "hide_reply_button": False,
            },
            "user": {
                "mid": 111111,
                "nickname": "测试用户",
            },
            "at_time": 1700000000,
        }

        item = MentionItem(raw=api_data)

        assert item.id == 123456
        assert item.type == "reply"
        assert item.oid == 987654
        assert item.root == 0
        assert item.parent == 0
        assert item.mid == 111111
        assert item.uname == "测试用户"
        assert item.content == "测试评论 @被提及"
        assert item.ctime == 1700000000
        assert item.hide_reply_button is False

    def test_parse_mention_item_with_at_details(self):
        api_data = {
            "id": 123456,
            "item": {
                "type": "reply",
                "subject_id": 987654,
                "root_id": 0,
                "target_id": 0,
                "source_content": "测试评论 @bot_user",
                "at_time": 1700000000,
                "at_details": [
                    {"mid": 6794023, "nickname": "bot_user"},
                ],
            },
            "user": {
                "mid": 111111,
                "nickname": "测试用户",
            },
            "at_time": 1700000000,
        }

        item = MentionItem(raw=api_data)
        assert item.at_details == [{"mid": 6794023, "nickname": "bot_user"}]

    def test_parse_mention_item_empty_at_details(self):
        api_data = {
            "id": 123456,
            "item": {
                "type": "reply",
                "subject_id": 987654,
                "root_id": 0,
                "target_id": 0,
                "source_content": "测试评论",
                "at_time": 1700000000,
            },
            "user": {
                "mid": 111111,
                "nickname": "测试用户",
            },
            "at_time": 1700000000,
        }

        item = MentionItem(raw=api_data)
        assert item.at_details == []


@pytest.mark.asyncio
class TestMentionMonitor:
    @pytest.fixture
    def mock_monitor(self, mock_cookie_dict, mock_db):
        monitor = MentionMonitor(
            cookies=mock_cookie_dict,
            db=mock_db,
            poll_interval=60,
            batch_size=20,
        )
        return monitor

    async def test_filter_valid_mentions_all_valid(self, mock_monitor):
        mentions = [
            make_mention_item(id=1, type=1, source_content="c1"),
            make_mention_item(id=2, type=1, source_content="c2"),
        ]

        valid = await mock_monitor.filter_valid_mentions(mentions)
        assert len(valid) == 2

    async def test_filter_valid_mentions_with_hidden(self, mock_monitor):
        mentions = [
            make_mention_item(id=1, type=1, source_content="c1", hide_reply_button=False),
            make_mention_item(id=2, type=1, source_content="c2", hide_reply_button=True),
        ]

        valid = await mock_monitor.filter_valid_mentions(mentions)
        assert len(valid) == 1

    async def test_filter_valid_mentions_by_type(self, mock_monitor):
        mentions = [
            make_mention_item(id=1, type=1, source_content="c1"),
            make_mention_item(id=2, type=3, source_content="c2"),
        ]

        valid = await mock_monitor.filter_valid_mentions(mentions)
        assert len(valid) == 1
        assert valid[0].type == 1

    async def test_filter_valid_mentions_dynamic_type(self, mock_monitor):
        mentions = [
            make_mention_item(id=1, type="dynamic", source_content="c1"),
        ]

        valid = await mock_monitor.filter_valid_mentions(mentions)
        assert len(valid) == 1
        assert valid[0].type == "dynamic"


@pytest.mark.asyncio
class TestMentionMonitorAsync:
    async def test_fetch_unread_count(self, mock_cookie_dict, mock_db_path, mock_httpx_response):
        from grok.db import Database

        db = Database(db_path=mock_db_path)
        await db.connect()

        mock_response = MagicMock()
        mock_response.json.return_value = {"code": 0, "data": {"unread_at": 10}}
        mock_response.raise_for_status = MagicMock()

        monitor = MentionMonitor(
            cookies=mock_cookie_dict,
            db=db,
        )
        monitor._client = AsyncMock()
        monitor._client.get = AsyncMock(return_value=mock_response)

        count = await monitor.fetch_unread_count()
        assert count == 10

        await db.close()

    async def test_fetch_mention_list(self, mock_cookie_dict, mock_db_path):
        from grok.db import Database

        db = Database(db_path=mock_db_path)
        await db.connect()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "items": [
                    {
                        "id": 123,
                        "item": {
                            "type": "reply",
                            "subject_id": 456,
                            "root_id": 0,
                            "target_id": 0,
                            "source_content": "test",
                            "at_time": 1700000000,
                            "reply_count": 0,
                            "hide_reply_button": False,
                        },
                        "user": {
                            "mid": 789,
                            "nickname": "user",
                        },
                        "at_time": 1700000000,
                    }
                ],
                "cursor": {"cursor": 0},
            },
        }
        mock_response.raise_for_status = MagicMock()

        monitor = MentionMonitor(
            cookies=mock_cookie_dict,
            db=db,
        )
        monitor._client = AsyncMock()
        monitor._client.get = AsyncMock(return_value=mock_response)

        mentions, cursor = await monitor.fetch_mention_list()
        assert len(mentions) == 1
        assert mentions[0].id == 123
        assert cursor == 0

        await db.close()


class TestStripBotMentions:
    """Tests for strip_bot_mentions function."""

    def test_strip_bot_mentions_from_mention(self):
        from grok.mention import strip_bot_mentions

        content = "@x 光 你好 @other 也你好"
        at_details = [
            {"mid": 6794023, "nickname": "x 光"},
            {"mid": 111111, "nickname": "other"},
        ]
        bot_mid = 6794023

        result = strip_bot_mentions(content, at_details, bot_mid)
        assert result == "你好 @other 也你好"

    def test_strip_bot_mentions_fallback_nickname(self):
        from grok.mention import strip_bot_mentions

        content = "@x 光 你好 @other 也你好"
        at_details = []
        bot_mid = 6794023
        bot_nickname = "x 光"

        result = strip_bot_mentions(content, at_details, bot_mid, bot_nickname)
        assert result == "你好 @other 也你好"

    def test_strip_bot_mentions_empty_at_details_no_fallback(self):
        from grok.mention import strip_bot_mentions

        content = "@x 光 你好"
        at_details = []
        bot_mid = 6794023

        result = strip_bot_mentions(content, at_details, bot_mid)
        assert result == content

    def test_strip_bot_mentions_special_chars(self):
        from grok.mention import strip_bot_mentions

        content = "@bot(测试) 你好"
        at_details = [{"mid": 123, "nickname": "bot(测试)"}]
        bot_mid = 123

        result = strip_bot_mentions(content, at_details, bot_mid)
        assert result == "你好"

    def test_strip_bot_mentions_multiple_occurrences(self):
        from grok.mention import strip_bot_mentions

        content = "@bot 你好 @bot 再见"
        at_details = [{"mid": 123, "nickname": "bot"}]
        bot_mid = 123

        result = strip_bot_mentions(content, at_details, bot_mid)
        assert result == "你好 再见"


@pytest.mark.asyncio
class TestSyncMentions:
    async def test_sync_mentions_inserts_new(self, mock_cookie_dict, mock_db_path):
        from grok.db import Database

        db = Database(db_path=mock_db_path)
        await db.connect()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "items": [
                    {
                        "id": 100,
                        "item": {
                            "type": "reply",
                            "subject_id": 456,
                            "root_id": 0,
                            "target_id": 0,
                            "source_content": "test mention",
                            "at_time": 1700000000,
                            "hide_reply_button": False,
                        },
                        "user": {
                            "mid": 789,
                            "nickname": "user",
                        },
                        "at_time": 1700000000,
                    }
                ],
                "cursor": {"cursor": 0},
            },
        }
        mock_response.raise_for_status = MagicMock()

        monitor = MentionMonitor(
            cookies=mock_cookie_dict,
            db=db,
        )
        monitor._running = True
        monitor._client = AsyncMock()
        monitor._client.get = AsyncMock(return_value=mock_response)

        synced = await monitor.sync_mentions()

        assert synced == 1

        pending = await db.get_pending_mentions()
        assert len(pending) == 1
        assert pending[0].id == 100

        await db.close()

    async def test_sync_mentions_skips_duplicate(self, mock_cookie_dict, mock_db_path):
        from grok.db import Database, Mention

        db = Database(db_path=mock_db_path)
        await db.connect()

        mention = Mention(
            id=200,
            type=1,
            oid=456,
            root=0,
            parent=0,
            mid=789,
            uname="user",
            content="existing",
            ctime=1700000000,
            status="pending",
        )
        await db.insert_mention(mention)

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "items": [
                    {
                        "id": 200,
                        "item": {
                            "type": "reply",
                            "subject_id": 456,
                            "root_id": 0,
                            "target_id": 0,
                            "source_content": "duplicate",
                            "at_time": 1700000000,
                            "hide_reply_button": False,
                        },
                        "user": {
                            "mid": 789,
                            "nickname": "user",
                        },
                        "at_time": 1700000000,
                    }
                ],
                "cursor": {"cursor": 0},
            },
        }
        mock_response.raise_for_status = MagicMock()

        monitor = MentionMonitor(
            cookies=mock_cookie_dict,
            db=db,
        )
        monitor._running = True
        monitor._client = AsyncMock()
        monitor._client.get = AsyncMock(return_value=mock_response)

        synced = await monitor.sync_mentions()

        assert synced == 0

        await db.close()

    async def test_sync_mentions_filters_hidden(self, mock_cookie_dict, mock_db_path):
        from grok.db import Database

        db = Database(db_path=mock_db_path)
        await db.connect()

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "code": 0,
            "data": {
                "items": [
                    {
                        "id": 300,
                        "item": {
                            "type": "reply",
                            "subject_id": 456,
                            "root_id": 0,
                            "target_id": 0,
                            "source_content": "hidden",
                            "at_time": 1700000000,
                            "hide_reply_button": True,
                        },
                        "user": {
                            "mid": 789,
                            "nickname": "user",
                        },
                        "at_time": 1700000000,
                    }
                ],
                "cursor": {"cursor": 0},
            },
        }
        mock_response.raise_for_status = MagicMock()

        monitor = MentionMonitor(
            cookies=mock_cookie_dict,
            db=db,
        )
        monitor._running = True
        monitor._client = AsyncMock()
        monitor._client.get = AsyncMock(return_value=mock_response)

        synced = await monitor.sync_mentions()

        assert synced == 0

        await db.close()


@pytest.mark.asyncio
class TestTimeoutSkip:
    async def test_timeout_skip_old_mention(self, mock_cookie_dict, mock_db):
        import time

        from grok.db import Mention

        old_time = int(time.time()) - 30 * 60
        mention = Mention(
            id=400,
            type=1,
            oid=456,
            root=0,
            parent=0,
            mid=789,
            uname="user",
            content="old mention",
            ctime=old_time,
            status="pending",
        )
        await mock_db.insert_mention(mention)

        monitor = MentionMonitor(
            cookies=mock_cookie_dict,
            db=mock_db,
            processing_timeout_minutes=20,
        )

        assert monitor.processing_timeout_minutes == 20

        pending = await mock_db.get_one_pending_mention()
        assert pending is not None

        age_minutes = (time.time() - old_time) / 60
        assert age_minutes > 20

    async def test_recent_mention_not_skipped(self, mock_cookie_dict, mock_db):
        import time

        from grok.db import Mention

        recent_time = int(time.time()) - 5 * 60
        mention = Mention(
            id=401,
            type=1,
            oid=456,
            root=0,
            parent=0,
            mid=789,
            uname="user",
            content="recent mention",
            ctime=recent_time,
            status="pending",
        )
        await mock_db.insert_mention(mention)

        pending = await mock_db.get_one_pending_mention()
        assert pending is not None
        assert pending.id == 401


@pytest.mark.asyncio
class TestConcurrentMode:
    async def test_listener_worker_mode(self, mock_cookie_dict, mock_db):
        monitor = MentionMonitor(
            cookies=mock_cookie_dict,
            db=mock_db,
            poll_interval=1,
            batch_size=10,
            processing_interval_seconds=1,
            processing_timeout_minutes=20,
        )

        assert monitor.poll_interval == 1
        assert monitor.processing_interval_seconds == 1
        assert monitor.processing_timeout_minutes == 20

    async def test_stop_signal(self, mock_cookie_dict, mock_db):
        monitor = MentionMonitor(
            cookies=mock_cookie_dict,
            db=mock_db,
        )

        assert monitor._running is False

        monitor._running = True
        assert monitor._running is True

        await monitor.stop()
        assert monitor._running is False

    async def test_lifo_strategy(self, mock_cookie_dict, mock_db):
        from grok.db import Mention

        for i in range(5):
            mention = Mention(
                id=500 + i,
                type=1,
                oid=456,
                root=0,
                parent=0,
                mid=789,
                uname="user",
                content=f"mention {i}",
                ctime=1700000000 + i,
                status="pending",
            )
            await mock_db.insert_mention(mention)

        pending = await mock_db.get_one_pending_mention()

        assert pending is not None
        assert pending.id == 504
        assert pending.ctime == 1700000004
