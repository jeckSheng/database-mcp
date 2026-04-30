from typing import Any
import aiomysql
import asyncpg
from .config import DatabaseConfig


class DatabasePool:
    """MySQL 和 PostgreSQL 连接池的统一抽象接口。"""

    def __init__(self, name: str, config: DatabaseConfig) -> None:
        self.name = name
        self.config = config
        self._pool: Any = None

    async def _ensure_connected(self) -> None:
        """懒加载：首次调用时才真正建立连接池。"""
        if self._pool is not None:
            return
        if self.config.type == "mysql":
            self._pool = await aiomysql.create_pool(
                host=self.config.host,
                port=self.config.port,
                db=self.config.database,
                user=self.config.user,
                password=self.config.password,
                autocommit=True,
                minsize=1,
                maxsize=5,
            )
        else:  # postgresql
            self._pool = await asyncpg.create_pool(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                min_size=1,
                max_size=5,
            )

    async def initialize(self) -> None:
        """保留此方法供外部调用，实际连接推迟到首次使用。"""
        pass

    async def close(self) -> None:
        """关闭连接池，释放资源。"""
        if self._pool is None:
            return
        if self.config.type == "mysql":
            self._pool.close()
            await self._pool.wait_closed()
        else:
            await self._pool.close()

    async def fetch_all(self, sql: str, params: list | None = None) -> list[dict]:
        await self._ensure_connected()
        """执行 SELECT，返回行字典列表，最多 max_rows 条。"""
        if self.config.type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await cur.execute(sql, params or ())
                    rows = await cur.fetchmany(self.config.max_rows)
                    return [dict(row) for row in rows]
        else:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(sql, *(params or []))
                return [dict(row) for row in rows[: self.config.max_rows]]

    async def execute(self, sql: str, params: list | None = None) -> str:
        await self._ensure_connected()
        """执行 DML/DDL，返回状态字符串。"""
        if self.config.type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(sql, params or ())
                    return f"{cur.rowcount} row(s) affected"
        else:
            async with self._pool.acquire() as conn:
                result = await conn.execute(sql, *(params or []))
                return str(result)

    async def fetch_tables(self) -> list[str]:
        await self._ensure_connected()
        """列出当前数据库的所有表名。"""
        if self.config.type == "mysql":
            rows = await self.fetch_all("SHOW TABLES")
            return [list(row.values())[0] for row in rows]
        else:
            rows = await self.fetch_all(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' ORDER BY tablename"
            )
            return [row["tablename"] for row in rows]

    async def describe_table(self, table: str) -> list[dict]:
        await self._ensure_connected()
        """返回指定表的列信息。调用方需提前校验 table 标识符合法性。"""
        if self.config.type == "mysql":
            return await self.fetch_all(f"DESCRIBE `{table}`")
        else:
            return await self.fetch_all(
                "SELECT column_name, data_type, is_nullable, column_default "
                "FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = $1 "
                "ORDER BY ordinal_position",
                [table],
            )
