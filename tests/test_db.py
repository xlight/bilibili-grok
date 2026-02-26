"""Tests for database module."""

import pytest

from grok.db import Database, Mention


@pytest.mark.asyncio
class TestDatabase:
    async def test_connect(self, mock_db_path):
        db = Database(db_path=mock_db_path)
        await db.connect()
        assert db._conn is not None
        await db.close()

    async def test_insert_mention_new(self, mock_db):
        mention = Mention(
            id=123456,
            type=1,
            oid=987654,
            root=0,
            parent=0,
            mid=111111,
            uname="测试用户",
            content="测试内容",
            ctime=1700000000,
            status="pending",
        )

        result = await mock_db.insert_mention(mention)
        assert result is True

    async def test_insert_mention_duplicate(self, mock_db):
        mention = Mention(
            id=123457,
            type=1,
            oid=987654,
            root=0,
            parent=0,
            mid=111111,
            uname="测试用户",
            content="测试内容",
            ctime=1700000000,
            status="pending",
        )

        await mock_db.insert_mention(mention)

        result = await mock_db.insert_mention(mention)
        assert result is False

    async def test_get_pending_mentions(self, mock_db):
        for i in range(3):
            mention = Mention(
                id=1000 + i,
                type=1,
                oid=987654,
                root=0,
                parent=0,
                mid=111111,
                uname="测试用户",
                content=f"测试内容 {i}",
                ctime=1700000000 + i,
                status="pending",
            )
            await mock_db.insert_mention(mention)

        pending = await mock_db.get_pending_mentions(limit=10)
        assert len(pending) == 3

    async def test_update_mention_status(self, mock_db):
        mention = Mention(
            id=2000,
            type=1,
            oid=987654,
            root=0,
            parent=0,
            mid=111111,
            uname="测试用户",
            content="测试内容",
            ctime=1700000000,
            status="pending",
        )

        await mock_db.insert_mention(mention)

        await mock_db.update_mention_status(
            2000,
            "replied",
            reply_content="回复内容",
        )

        updated = await mock_db.get_mention_by_id(2000)
        assert updated.status == "replied"
        assert updated.reply_content == "回复内容"

    async def test_get_stats(self, mock_db_path):
        from grok.db import Database

        db = Database(db_path=mock_db_path)
        await db.connect()

        await db._conn.execute("DELETE FROM mentions")
        await db._conn.commit()

        mentions = [
            Mention(
                id=13000,
                type=1,
                oid=1,
                root=0,
                parent=0,
                mid=1,
                uname="u1",
                content="c1",
                ctime=1,
                status="pending",
            ),
            Mention(
                id=13001,
                type=1,
                oid=1,
                root=0,
                parent=0,
                mid=1,
                uname="u2",
                content="c2",
                ctime=2,
                status="replied",
            ),
            Mention(
                id=13002,
                type=1,
                oid=1,
                root=0,
                parent=0,
                mid=1,
                uname="u3",
                content="c3",
                ctime=3,
                status="failed",
            ),
        ]

        for m in mentions:
            await db.insert_mention(m)

        stats = await db.get_stats()

        assert stats["total"] == 3
        assert stats["pending"] == 1
        assert stats["replied"] == 1
        assert stats["failed"] == 1

        await db.close()

    async def test_get_mention_by_id_not_found(self, mock_db):
        result = await mock_db.get_mention_by_id(999999)
        assert result is None

    async def test_get_one_pending_mention_lifo(self, mock_db):
        await mock_db._conn.execute("DELETE FROM mentions")
        await mock_db._conn.commit()

        for i in range(5):
            mention = Mention(
                id=5000 + i,
                type=1,
                oid=987654,
                root=0,
                parent=0,
                mid=111111,
                uname="测试用户",
                content=f"测试内容 {i}",
                ctime=1700000000 + i,
                status="pending",
            )
            await mock_db.insert_mention(mention)

        result = await mock_db.get_one_pending_mention()
        assert result is not None
        assert result.id == 5004
        assert result.ctime == 1700000004

    async def test_get_one_pending_mention_empty(self, mock_db):
        await mock_db._conn.execute("DELETE FROM mentions")
        await mock_db._conn.commit()

        result = await mock_db.get_one_pending_mention()
        assert result is None

    async def test_get_one_pending_mention_filters_by_status(self, mock_db):
        await mock_db._conn.execute("DELETE FROM mentions")
        await mock_db._conn.commit()

        mention1 = Mention(
            id=16000,
            type=1,
            oid=987654,
            root=0,
            parent=0,
            mid=111111,
            uname="测试用户",
            content="pending",
            ctime=1700100000,
            status="pending",
        )
        mention2 = Mention(
            id=16001,
            type=1,
            oid=987654,
            root=0,
            parent=0,
            mid=111111,
            uname="测试用户",
            content="replied",
            ctime=1700100001,
            status="replied",
        )
        await mock_db.insert_mention(mention1)
        await mock_db.insert_mention(mention2)

        result = await mock_db.get_one_pending_mention()
        assert result is not None
        assert result.id == 16000

    async def test_insert_mention_with_at_details(self, mock_db):
        at_details = [
            {"mid": 123456, "nickname": "bot_user"},
            {"mid": 789012, "nickname": "other_user"},
        ]
        mention = Mention(
            id=7000,
            type=1,
            oid=987654,
            root=0,
            parent=0,
            mid=111111,
            uname="测试用户",
            content="测试 @bot_user",
            ctime=1700000000,
            status="pending",
            at_details=at_details,
        )

        result = await mock_db.insert_mention(mention)
        assert result is True

        retrieved = await mock_db.get_mention_by_id(7000)
        assert retrieved.at_details == at_details

    async def test_insert_mention_without_at_details(self, mock_db):
        mention = Mention(
            id=7001,
            type=1,
            oid=987654,
            root=0,
            parent=0,
            mid=111111,
            uname="测试用户",
            content="测试内容",
            ctime=1700000000,
            status="pending",
            at_details=None,
        )

        result = await mock_db.insert_mention(mention)
        assert result is True

        retrieved = await mock_db.get_mention_by_id(7001)
        assert retrieved.at_details is None


@pytest.mark.asyncio
class TestMentionModel:
    def test_mention_creation(self):
        mention = Mention(
            id=123,
            type=1,
            oid=456,
            root=0,
            parent=0,
            mid=789,
            uname="用户",
            content="内容",
            ctime=1700000000,
            status="pending",
        )

        assert mention.id == 123
        assert mention.type == 1
        assert mention.status == "pending"
