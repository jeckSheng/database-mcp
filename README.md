# 多数据库配置 MCP

让 Claude Code / Claude Desktop 等 AI 客户端通过 MCP 协议直接操作多个 MySQL / PostgreSQL 数据库。每个连接独立配置读/写/DDL 权限，密码通过环境变量管理。

## 功能

| MCP 工具 | 说明 | 权限要求 |
|----------|------|----------|
| `list_connections` | 列出所有数据库连接及权限 | 无 |
| `execute_query` | 执行单条只读 SELECT（最多 1000 行） | `allow_read` |
| `execute_write` | 执行单条 INSERT / UPDATE / DELETE | `allow_write` |
| `execute_ddl` | 执行 CREATE / ALTER / DROP 等 DDL | `allow_ddl` |
| `list_tables` | 列出数据库所有表 | `allow_read` |
| `describe_table` | 查看表结构 | `allow_read` |

## 快速开始

### 1. 配置数据库连接

```bash
cp databases.example.yaml databases.yaml  # databases.yaml 是本地配置，不提交 git
```

编辑 `databases.yaml`，填入你的数据库信息：

```yaml
databases:
  my_mysql:
    type: mysql
    host: 192.168.1.10
    port: 3306
    database: myapp
    user: readonly_user
    password: "${MYSQL_PASSWORD}"   # 从环境变量读取
    permissions:
      allow_read: true
      allow_write: false
      allow_ddl: false

  my_pg:
    type: postgresql
    host: 192.168.1.20
    port: 5432
    database: analytics
    user: analyst
    password: "${PG_PASSWORD}"
    permissions:
      allow_read: true
      allow_write: true
      allow_ddl: false
```

### 2. 配置密码

```bash
cp .env.example .env
# 编辑 .env，填入真实密码
```

`.env` 内容示例：
```bash
MYSQL_PASSWORD=your_mysql_password
PG_PASSWORD=your_pg_password
```

### 3. 启动容器

```bash
docker-compose build
docker-compose up -d
```

### 4. 注册到 Claude Code

```bash
claude mcp add database  --scope user  -- docker exec -i database-mcp python -m database_mcp
```

验证注册成功：
```bash
claude mcp list
```

启动 Claude Code 后即可直接对话使用。

## 配置说明

### 权限控制

每个连接支持三级权限，独立配置：

| 权限字段 | 默认值 | 说明 |
|----------|--------|------|
| `allow_read` | `true` | 允许 SELECT 查询 |
| `allow_write` | `false` | 允许 INSERT / UPDATE / DELETE |
| `allow_ddl` | `false` | 允许 CREATE / ALTER / DROP / TRUNCATE |

安全机制：
- SQL 经 sqlglot 按方言解析，每次只允许一条语句，语句类型须与工具匹配，无法解析的直接拒绝；MySQL 禁用 `/*! */` 可执行注释和 `/*+ */` 优化器提示
- `execute_query` 在只读事务中执行，拒绝 `SELECT ... INTO`、PG 数据修改 CTE 等写操作
- `execute_write` 拒绝不带 WHERE 的 UPDATE / DELETE 和 WITH 中的写操作；在事务中执行，影响行数超过上限即回滚
- 表名做标识符校验，防止 SQL 注入

> 以上是防误操作，不是安全边界。`GET_LOCK()`、`dblink_exec()` 这类函数的副作用不受只读事务限制，只读连接请使用只读数据库账号，真正的权限隔离靠数据库授权。

可选限制（每个连接单独配置）：

| 字段 | 默认值 | 说明 |
|------|--------|------|
| `max_rows` | `1000` | 查询最多返回行数 |
| `max_affected_rows` | `1000` | 单条写操作影响行数上限，超过则回滚（MyISAM 等非事务表无法回滚） |
| `statement_timeout` | `30` | 语句超时秒数，`0` 为不限制。PG 作用于查询和写操作；MySQL 仅作用于查询，服务端不支持时自动跳过；均不限制 DDL |

### 环境变量占位符

密码字段支持 `${VAR_NAME}` 语法，运行时从环境变量读取，避免明文写入配置文件：

```yaml
password: "${MY_DB_PASSWORD}"
```

## 项目结构

```
database-mcp/
├── databases.yaml          # 数据库连接配置（不提交 git）
├── databases.example.yaml  # 连接配置模板
├── .env                    # 密码环境变量（不提交 git）
├── .env.example            # 环境变量模板
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── src/
    └── database_mcp/
        ├── config.py       # 配置加载 & 校验
        ├── guard.py        # 权限检查 & SQL 安全过滤
        ├── pool.py         # MySQL/PostgreSQL 连接池
        ├── router.py       # 按连接名路由
        ├── main.py         # MCP Server 入口
        └── tools/
            ├── query.py    # execute_query / execute_write / execute_ddl
            └── schema.py   # list_connections / list_tables / describe_table
```

## 开发

```bash
# 安装依赖（在 docker-python-platform python311 容器内）
pip install -e ".[dev]"

# 运行测试
pytest -v
```

## 常见问题

**修改 `databases.yaml` 后不生效？**  
需要重启容器：`docker-compose restart`

**容器已启动但 Claude Code 连不上？**  
确认容器名称是 `database-mcp`：`docker ps | grep database-mcp`

**想让容器开机自动启动？**  
`docker-compose.yml` 已配置 `restart: unless-stopped`，重启 Docker Desktop 后自动恢复。
