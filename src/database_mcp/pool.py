import logging
from typing import Any
import aiomysql
import asyncpg
from .config import DatabaseConfig
from .guard import SQLSafetyError

logger = logging.getLogger("database-mcp")


def _check_affected(rowcount: int, limit: int) -> None:
    if rowcount > limit:
        raise SQLSafetyError(
            f"影响 {rowcount} 行，超过上限 {limit} 行（max_affected_rows），已回滚。"
            f"请缩小 WHERE 范围或分批执行。"
        )


class DatabasePool:
    """MySQL 和 PostgreSQL 连接池的统一抽象接口。"""

    def __init__(self, name: str, config: DatabaseConfig) -> None:
        self.name = name
        self.config = config
        self._pool: Any = None
        self._mysql_timeout_supported = True

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

    async def _set_pg_timeout(self, conn: Any) -> None:
        """事务内设置超时，不影响 DDL，也兼容 PgBouncer。"""
        await conn.execute(
            f"SET LOCAL statement_timeout = {self.config.statement_timeout * 1000}"
        )

    async def _set_mysql_timeout(self, cur: Any) -> None:
        """设置会话级 SELECT 超时；MariaDB 等不支持该变量时降级为不设超时。"""
        if not self._mysql_timeout_supported:
            return
        try:
            await cur.execute(
                f"SET SESSION max_execution_time = {self.config.statement_timeout * 1000}"
            )
        except aiomysql.Error as e:
            if e.args[0] != 1193:  # 1193: Unknown system variable
                raise
            self._mysql_timeout_supported = False
            logger.warning(f"[{self.name}] 不支持 max_execution_time，查询将不设超时: {e}")

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
        """在只读事务中执行 SELECT，返回行字典列表，最多 max_rows 条。"""
        if self.config.type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor(aiomysql.DictCursor) as cur:
                    await self._set_mysql_timeout(cur)
                    await cur.execute("START TRANSACTION READ ONLY")
                    try:
                        await cur.execute(sql, params)
                        rows = await cur.fetchmany(self.config.max_rows)
                    finally:
                        if not conn.closed:  # 任务取消时 aiomysql 会关闭连接
                            await conn.rollback()
                    return [dict(row) for row in rows]
        else:
            async with self._pool.acquire() as conn:
                async with conn.transaction(readonly=True):
                    await self._set_pg_timeout(conn)
                    rows = await conn.fetch(sql, *(params or []))
                return [dict(row) for row in rows[: self.config.max_rows]]

    async def execute(
        self,
        sql: str,
        params: list | None = None,
        max_affected_rows: int | None = None,
    ) -> str:
        await self._ensure_connected()
        """执行 DML/DDL，返回状态字符串。
        传入 max_affected_rows 时在事务中执行，影响行数超限则回滚并抛 SQLSafetyError。"""
        if self.config.type == "mysql":
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cur:
                    if max_affected_rows is None:
                        await cur.execute(sql, params)
                        return f"{cur.rowcount} row(s) affected"
                    await conn.begin()
                    try:
                        await cur.execute(sql, params)
                        _check_affected(cur.rowcount, max_affected_rows)
                        await conn.commit()
                    except BaseException:
                        if not conn.closed:
                            await conn.rollback()
                        raise
                    return f"{cur.rowcount} row(s) affected"
        else:
            async with self._pool.acquire() as conn:
                if max_affected_rows is None:
                    result = await conn.execute(sql, *(params or []))
                    return str(result)
                async with conn.transaction():
                    await self._set_pg_timeout(conn)
                    # prepare 走扩展协议，服务端只接受单条语句
                    stmt = await conn.prepare(sql)
                    await stmt.fetch(*(params or []))
                    status = stmt.get_statusmsg()
                    _check_affected(int(status.split()[-1]), max_affected_rows)
                return status

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
