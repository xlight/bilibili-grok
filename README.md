# Bilibili Grok

B站 @mention 自动回复机器人，使用 AI（LangGraph + LLM）自动生成回复。

## 功能特性

- 🤖 **自动回复**：监听 B站 @mention，使用 AI 自动生成回复
- 🔐 **扫码登录**：支持二维码登录，凭证自动保存
- 📊 **状态追踪**：SQLite 数据库记录所有 mentions 状态
- 🏥 **健康检查**：内置 HTTP 健康检查端点
- 📝 **完整日志**：结构化日志，支持 JSON 格式
- 🐳 **Docker 部署**：支持容器化部署

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

详细指南见：[docs/快速开始.md](docs/快速开始.md)

## 配置说明

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `agent.model` | LLM 模型 | `openai/gpt-4o-mini` |
| `agent.api_key` | API Key | 环境变量 `LITELLM_API_KEY` |
| `monitor.poll_interval` | 轮询间隔(秒) | 60 |
| `monitor.batch_size` | 批处理数量 | 20 |
| `health.port` | 健康检查端口 | 8080 |

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
