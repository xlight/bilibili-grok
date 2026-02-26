# Bilibili Grok

B站 @mention 自动回复机器人，使用 AI（LangGraph + LLM）自动生成回复。

## 功能特性

- 🤖 **自动回复**：监听 B站 @mention，使用 AI 自动生成回复
- 🔐 **扫码登录**：支持二维码登录，凭证自动保存
- 📊 **状态追踪**：SQLite 数据库记录所有 mentions 状态
- 🏥 **健康检查**：内置 HTTP 健康检查端点
- 📝 **完整日志**：结构化日志，支持 JSON 格式
- 🐳 **Docker 部署**：支持容器化部署
- ⚡ **并发处理**：监听和处理独立运行，互不阻塞

## 快速开始

```bash
# 1. 安装依赖
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. 配置
cp config.yaml config.yaml.bak
# 编辑 config.yaml，填入 API Key

# 3. 运行（首次需扫码登录）
PYTHONPATH=src python -m grok.main
```

## Docker 部署

```bash
# 构建并运行（使用当前目录的 config.yaml）
docker build -t bilibili-grok .
docker run -d --name grok \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/config.yaml:/app/config.yaml \
  -e GROK_AGENT_API_KEY=your-api-key \
  -e SEARCH_API_KEY=your-search-key \
  bilibili-grok

# 或使用 Docker Compose（推荐）
cp .env.template .env
# 编辑 .env 文件
docker-compose up -d
```

**生产部署**：

1. 使用预构建的镜像：
    ```bash
    export GITHUB_USERNAME=your-username
    export GROK_AGENT_API_KEY=your-api-key
    docker-compose -f docker-compose.prod.yml up -d
    ```

2. 镜像自动构建：每次推送到 main 分支或发布新版本时，GitHub Action 会自动构建并推送到 `ghcr.io/{username}/bilibili-grok`

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `agent.model` | LLM 模型 | `openai/gpt-4o-mini` |
| `agent.api_base` | API 基础URL | `https://api.openai.com/v1` |
| `agent.api_key` | API Key | 环境变量 `LITELLM_API_KEY` |
| `monitor.poll_interval` | 轮询间隔 (秒) | 60 |
| `monitor.batch_size` | 批处理数量 | 20 |
| `monitor.processing_interval_seconds` | 处理间隔 (秒) | 20 |
| `monitor.processing_timeout_minutes` | 超时跳过阈值 (分钟) | 20 |
| `reply.rate_limit_seconds` | 回复速率限制 (秒) | 3 |
| `reply.max_retries` | 最大重试次数 | 3 |
| `health.port` | 健康检查端口 | 8080 |

**环境变量覆盖**：所有配置项都支持环境变量覆盖，格式为 `GROK_XXX_YYY`，例如：
- `GROK_AGENT_MODEL=gpt-4` 覆盖模型
- `GROK_AGENT_API_KEY=sk-xxx` 覆盖 API KEY
- `GROK_AGENT_API_BASE=https://api.example.com/v1` 覆盖 API 地址
- `GROK_MONITOR_POLL_INTERVAL=120` 覆盖轮询间隔
- `GROK_MONITOR_BATCH_SIZE=30` 覆盖批处理数量
- `GROK_MONITOR_PROCESSING_INTERVAL_SECONDS=30` 覆盖处理间隔
- `GROK_MONITOR_PROCESSING_TIMEOUT_MINUTES=30` 覆盖超时阈值
- `GROK_REPLY_RATE_LIMIT_SECONDS=5` 覆盖速率限制
- `GROK_REPLY_MAX_RETRIES=5` 覆盖最大重试次数
- `GROK_HEALTH_PORT=9090` 覆盖健康检查端口
- `GROK_LOGGING_LEVEL=DEBUG` 覆盖日志级别

**Docker 部署**：使用 Docker Compose 部署时，可以通过 `.env` 文件或环境变量传入敏感配置：

```yaml
environment:
  - GROK_AGENT_API_KEY=your-api-key
  - GROK_SEARCH_API_KEY=your-search-key
  - GROK_MONITOR_POLL_INTERVAL=30
  - GROK_MONITOR_PROCESSING_INTERVAL_SECONDS=15
  - GROK_MONITOR_PROCESSING_TIMEOUT_MINUTES=30
```

详细指南见：[docs/快速开始.md](docs/快速开始.md)

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `agent.model` | LLM 模型 | `openai/gpt-4o-mini` |
| `agent.api_base` | API 基础URL | `https://api.openai.com/v1` |
| `agent.api_key` | API Key | 环境变量 `LITELLM_API_KEY` |
| `monitor.poll_interval` | 轮询间隔 (秒) | 60 |
| `monitor.batch_size` | 批处理数量 | 20 |
| `monitor.processing_interval_seconds` | 处理间隔 (秒) | 20 |
| `monitor.processing_timeout_minutes` | 超时跳过阈值 (分钟) | 20 |
| `reply.rate_limit_seconds` | 回复速率限制 (秒) | 3 |
| `reply.max_retries` | 最大重试次数 | 3 |
| `health.port` | 健康检查端口 | 8080 |

**环境变量覆盖**：所有配置项都支持环境变量覆盖，格式为 `GROK_XXX_YYY`，例如：
- `GROK_AGENT_MODEL=gpt-4` 覆盖模型
- `GROK_AGENT_API_KEY=sk-xxx` 覆盖 API KEY
- `GROK_AGENT_API_BASE=https://api.example.com/v1` 覆盖 API 地址
- `GROK_MONITOR_POLL_INTERVAL=120` 覆盖轮询间隔
- `GROK_MONITOR_BATCH_SIZE=30` 覆盖批处理数量
- `GROK_MONITOR_PROCESSING_INTERVAL_SECONDS=30` 覆盖处理间隔
- `GROK_MONITOR_PROCESSING_TIMEOUT_MINUTES=30` 覆盖超时阈值
- `GROK_REPLY_RATE_LIMIT_SECONDS=5` 覆盖速率限制
- `GROK_REPLY_MAX_RETRIES=5` 覆盖最大重试次数
- `GROK_HEALTH_PORT=9090` 覆盖健康检查端口
- `GROK_LOGGING_LEVEL=DEBUG` 覆盖日志级别

**Docker 部署**：使用 Docker Compose 部署时，可以通过 `.env` 文件或环境变量传入敏感配置：

```yaml
environment:
  - GROK_AGENT_API_KEY=your-api-key
  - GROK_SEARCH_API_KEY=your-search-key
  - GROK_MONITOR_POLL_INTERVAL=30
  - GROK_MONITOR_PROCESSING_INTERVAL_SECONDS=15
  - GROK_MONITOR_PROCESSING_TIMEOUT_MINUTES=30
```

## 项目结构

```
src/grok/
├── main.py      # 入口
├── login.py     # 扫码登录
├── mention.py   # @mention 监控
├── reply.py     # 评论回复
├── agent.py     # LangGraph AI Agent
├── db.py        # SQLite 存储
├── config.py    # 配置管理
├── logger.py    # 日志
└── health.py    # 健康检查
```

## 技术栈

- **Python 3.10+**
- **LangGraph** - AI Agent 框架
- **httpx** - HTTP 客户端
- **aiosqlite** - 异步 SQLite
- **qrcode** - 二维码生成
- **aiohttp** - 健康检查服务

## 参考

- [bilibili-API-collect](https://github.com/SocialSisterYi/bilibili-API-collect)
- [bilibili-api](https://github.com/Nemo2011/bilibili-api)
