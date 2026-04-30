# 多数据库配置 MCP

让 Claude Code / Claude Desktop 等 AI 客户端通过 MCP 协议直接操作多个 MySQL / PostgreSQL 数据库。每个连接独立配置读/写/DDL 权限，密码通过环境变量管理。

## 功能

| MCP 工具 | 说明 | 权限要求 |
|----------|------|----------|
| `list_connections` | 列出所有数据库连接及权限 | 无 |
| `execute_query` | 执行 SELECT 查询（最多 1000 行） | `allow_read` |
| `execute_write` | 执行 INSERT / UPDATE / DELETE | `allow_write` |
| `execute_ddl` | 执行 CREATE / ALTER / DROP 等 DDL | `allow_ddl` |
| `list_tables` | 列出数据库所有表 | `allow_read` |
| `describe_table` | 查看表结构 | `allow_read` |

## 快速开始

### 1. 配置数据库连接

```bash
cp databases.yaml.example databases.yaml  # 或直接编辑 databases.yaml
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
claude mcp add database -- docker exec -i database-mcp python -m database_mcp
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
- `execute_query` 只接受 SELECT，传入其他语句直接报错
- `execute_write` 禁止 DROP / TRUNCATE（必须走 `execute_ddl`）
- 表名做标识符校验，防止 SQL 注入
- 查询结果默认最多返回 1000 行（可在配置中调整 `max_rows`）

### 环境变量占位符

密码字段支持 `${VAR_NAME}` 语法，运行时从环境变量读取，避免明文写入配置文件：

```yaml
password: "${MY_DB_PASSWORD}"
```

## 项目结构

```
database-mcp/
├── databases.yaml          # 数据库连接配置
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
