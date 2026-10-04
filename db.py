"""SQLite async — simpan mapping user -> deployment."""
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS deployments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    project_name TEXT NOT NULL,
    url TEXT NOT NULL,
    provider TEXT NOT NULL,
    telegram_token TEXT NOT NULL,
    telegram_chat_id TEXT NOT NULL,
    target_redirect TEXT NOT NULL,
    operator_tag TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_user ON deployments(user_id);
CREATE INDEX IF NOT EXISTS idx_project ON deployments(project_name);
CREATE INDEX IF NOT EXISTS idx_created ON deployments(created_at);
"""


class DB:
    def __init__(self, path: str):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def insert_deploy(self, **kw) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                """INSERT INTO deployments
                   (user_id, username, project_name, url, provider,
                    telegram_token, telegram_chat_id, target_redirect, operator_tag)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    kw["user_id"], kw.get("username"), kw["project_name"], kw["url"],
                    kw["provider"], kw["telegram_token"], kw["telegram_chat_id"],
                    kw["target_redirect"], kw.get("operator_tag"),
                ),
            )
            await db.commit()
            return cur.lastrowid

    async def list_user_deploys(self, user_id: int, limit: int = 20):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM deployments WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            )
            return await cur.fetchall()

    async def get_deploy(self, deploy_id: int):
        async with aiosqlite.connect(self.path) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT * FROM deployments WHERE id=?", (deploy_id,)
            )
            return await cur.fetchone()

    async def count_today(self, user_id: int) -> int:
        async with aiosqlite.connect(self.path) as db:
            cur = await db.execute(
                "SELECT COUNT(*) FROM deployments "
                "WHERE user_id=? AND date(created_at)=date('now')",
                (user_id,),
            )
            row = await cur.fetchone()
            return row[0] if row else 0
