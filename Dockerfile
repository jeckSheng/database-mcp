FROM python:3.11-slim

WORKDIR /app

# 先复制依赖文件，利用 Docker 层缓存
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# databases.yaml 通过 volume 挂载，不打包进镜像
# 容器以 stdio 模式运行，由 Claude 客户端通过 docker exec -i 调用
CMD ["python", "-m", "database_mcp"]
