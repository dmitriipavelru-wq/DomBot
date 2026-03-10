import asyncpg
from config import DATABASE_URL

_pool = None

async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL)
    return _pool

async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                name TEXT,
                family_id INTEGER,
                is_admin BOOLEAN DEFAULT FALSE
            );

            CREATE TABLE IF NOT EXISTS families (
                id SERIAL PRIMARY KEY,
                name TEXT,
                invite_code TEXT UNIQUE
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                family_id INTEGER,
                assigned_to BIGINT,
                created_by BIGINT,
                text TEXT,
                remind_at TIMESTAMP,
                done BOOLEAN DEFAULT FALSE,
                reminded BOOLEAN DEFAULT FALSE
            );
        """)

async def get_user(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE id=$1", user_id)

async def create_user(user_id: int, name: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO users(id, name) VALUES($1,$2) ON CONFLICT(id) DO NOTHING",
            user_id, name
        )

async def set_user_family(user_id: int, family_id: int, is_admin: bool = False):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE users SET family_id=$1, is_admin=$2 WHERE id=$3",
            family_id, is_admin, user_id
        )

async def create_family(name: str, invite_code: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO families(name, invite_code) VALUES($1,$2) RETURNING id",
            name, invite_code
        )
        return row["id"]

async def get_family_by_code(code: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM families WHERE invite_code=$1", code)

async def get_family(family_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM families WHERE id=$1", family_id)

async def get_family_members(family_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users WHERE family_id=$1", family_id)

async def create_task(family_id: int, assigned_to: int, created_by: int, text: str, remind_at):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """INSERT INTO tasks(family_id, assigned_to, created_by, text, remind_at)
               VALUES($1,$2,$3,$4,$5) RETURNING id""",
            family_id, assigned_to, created_by, text, remind_at
        )
        return row["id"]

async def get_pending_reminders():
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            """SELECT * FROM tasks
               WHERE remind_at <= NOW() AND done=FALSE AND reminded=FALSE"""
        )

async def mark_reminded(task_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tasks SET reminded=TRUE WHERE id=$1", task_id)

async def mark_done(task_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tasks SET done=TRUE WHERE id=$1", task_id)

async def get_family_tasks(family_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM tasks WHERE family_id=$1 ORDER BY remind_at",
            family_id
        )

async def get_user_tasks(user_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(
            "SELECT * FROM tasks WHERE assigned_to=$1 AND done=FALSE ORDER BY remind_at",
            user_id
        )
