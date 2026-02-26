"""SQLite database for mention tracking."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import aiosqlite


@dataclass
class Mention:
    """Represents a @mention."""

    id: int
    type: int
    oid: int
    root: int
    parent: int
    mid: int
    uname: str
    content: str
    ctime: int
    status: str
    reply_content: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    at_details: list[dict] | None = None  # List of mentioned users


class Database:
    """SQLite database for mention tracking."""

    def __init__(self, db_path: str = "data/grok.db"):
        self.db_path = Path(db_path)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to database."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._initialize()

    async def close(self) -> None:
        """Close database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _initialize(self) -> None:
        """Create tables if not exist."""
        await self._conn.execute("""
            CREATE TABLE IF NOT EXISTS mentions (
                id INTEGER PRIMARY KEY,
                type INTEGER NOT NULL,
                oid INTEGER NOT NULL,
                root INTEGER DEFAULT 0,
                parent INTEGER DEFAULT 0,
                mid INTEGER NOT NULL,
                uname TEXT NOT NULL,
                content TEXT NOT NULL,
                ctime INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                reply_content TEXT,
                at_details TEXT,  -- JSON array of mentioned users
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mentions_status
            ON mentions(status)
        """)

        await self._conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_mentions_oid
            ON mentions(oid)
        """)

        await self._conn.commit()

        # Migration: add at_details column if not exists (for existing databases)
        try:
            await self._conn.execute("ALTER TABLE mentions ADD COLUMN at_details TEXT")
            await self._conn.commit()
        except aiosqlite.OperationalError:
            # Column already exists
            pass

    async def insert_mention(self, mention: Mention) -> bool:
        """Insert mention with deduplication.

        Returns:
            True if inserted, False if already exists
        """
        try:
            # Convert at_details to JSON string if present
            import json

            at_details_json = json.dumps(mention.at_details) if mention.at_details else None

            await self._conn.execute(
                """
                INSERT INTO mentions
                    (id, type, oid, root, parent, mid, uname, content, ctime, status, at_details)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    mention.id,
                    mention.type,
                    mention.oid,
                    mention.root,
                    mention.parent,
                    mention.mid,
                    mention.uname,
                    mention.content,
                    mention.ctime,
                    mention.status,
                    at_details_json,
                ),
            )
            await self._conn.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def get_pending_mentions(self, limit: int = 20) -> list[Mention]:
        """Get pending mentions to process."""
        cursor = await self._conn.execute(
            """
            SELECT * FROM mentions
            WHERE status = 'pending'
            ORDER BY ctime ASC
            LIMIT ?
        """,
            (limit,),
        )

        rows = await cursor.fetchall()
        return [self._row_to_mention(row) for row in rows]

    async def get_one_pending_mention(self) -> Mention | None:
        """Get one pending mention (LIFO strategy - newest first)."""
        cursor = await self._conn.execute(
            """
            SELECT * FROM mentions
            WHERE status = 'pending'
            ORDER BY ctime DESC
            LIMIT 1
        """,
        )

        row = await cursor.fetchone()
        return self._row_to_mention(row) if row else None

    async def get_mention_by_id(self, mention_id: int) -> Mention | None:
        """Get mention by ID."""
        cursor = await self._conn.execute(
            """
            SELECT * FROM mentions WHERE id = ?
        """,
            (mention_id,),
        )

        row = await cursor.fetchone()
        return self._row_to_mention(row) if row else None

    async def update_mention_status(
        self,
        mention_id: int,
        status: str,
        reply_content: str | None = None,
    ):
        """Update mention status and optional reply content."""
        await self._conn.execute(
            """
            UPDATE mentions
            SET status = ?, reply_content = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """,
            (status, reply_content, mention_id),
        )
        await self._conn.commit()

    async def get_stats(self) -> dict:
        """Get database statistics."""
        cursor = await self._conn.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END) as processing,
                SUM(CASE WHEN status = 'replied' THEN 1 ELSE 0 END) as replied,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM mentions
        """)
        row = await cursor.fetchone()
        return dict(row) if row else {}

    def _row_to_mention(self, row: aiosqlite.Row) -> Mention:
        """Convert database row to Mention object."""
        import json

        at_details = None
        if row["at_details"]:
            try:
                at_details = json.loads(row["at_details"])
            except json.JSONDecodeError:
                at_details = None

        return Mention(
            id=row["id"],
            type=row["type"],
            oid=row["oid"],
            root=row["root"],
            parent=row["parent"],
            mid=row["mid"],
            uname=row["uname"],
            content=row["content"],
            ctime=row["ctime"],
            status=row["status"],
            reply_content=row["reply_content"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            at_details=at_details,
        )
