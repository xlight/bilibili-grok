"""Test fixtures for Bilibili Grok tests."""

import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_credentials():
    """Mock credentials data."""
    return {
        "sessdata": "test_sessdata_abc123",
        "bili_jct": "test_bili_jct_xyz789",
        "buvid3": "test_buvid3_def456",
        "dedeuserid": "12345678",
        "expires_at": (datetime.now() + timedelta(days=30)).isoformat(),
    }


@pytest.fixture
def mock_httpx_client():
    """Create a mock httpx.AsyncClient."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def sample_api_mention_response():
    """Sample API mention response matching real Bilibili API structure."""
    return {
        "id": 123456,
        "item": {
            "type": "reply",
            "subject_id": 987654,
            "root_id": 0,
            "target_id": 0,
            "source_content": "测试评论 @被提及",
            "at_time": 1700000000,
            "reply_count": 5,
            "hide_reply_button": False,
            "at_details": [
                {"mid": 6794023, "nickname": "bot_user"},
            ],
        },
        "user": {
            "mid": 111111,
            "nickname": "测试用户",
        },
        "at_time": 1700000000,
    }


@pytest.fixture
def mock_mention_item(sample_api_mention_response):
    """Create a correctly constructed MentionItem."""
    from grok.mention import MentionItem

    return MentionItem(raw=sample_api_mention_response)


@pytest.fixture
def mock_agent_config():
    """Create a mock AgentConfig."""
    from grok.agent import AgentConfig

    return AgentConfig(
        model="openai/gpt-4o-mini",
        api_base="https://api.openai.com/v1",
        api_key="test-api-key",
        max_tokens=500,
        temperature=0.7,
        system_prompt="You are a helpful assistant.",
    )


@pytest.fixture
def mock_credentials_file(tmp_path, mock_credentials):
    """Create a temporary credentials file."""
    cred_file = tmp_path / "credentials.json"
    cred_file.write_text(json.dumps(mock_credentials))
    return cred_file


@pytest.fixture
def mock_cookie_dict(mock_credentials):
    """Mock cookies dict."""
    return {
        "SESSDATA": mock_credentials["sessdata"],
        "bili_jct": mock_credentials["bili_jct"],
        "buvid3": mock_credentials["buvid3"],
        "DedeUserID": mock_credentials["dedeuserid"],
    }


@pytest.fixture
def mock_db_path(tmp_path):
    """Mock database path."""
    return str(tmp_path / "grok.db")


@pytest.fixture
def sample_config():
    """Sample configuration dict."""
    return {
        "bilibili": {
            "credential_path": "data/credentials.json",
        },
        "monitor": {
            "poll_interval": 60,
            "batch_size": 20,
            "processing_interval_seconds": 20,
            "processing_timeout_minutes": 20,
        },
        "reply": {
            "rate_limit_seconds": 3,
            "max_retries": 3,
        },
        "agent": {
            "model": "openai/gpt-4o-mini",
            "api_base": "https://api.openai.com/v1",
            "api_key": "test-api-key",
            "max_tokens": 500,
            "temperature": 0.7,
            "system_prompt": "You are a helpful assistant.",
        },
        "tools": {
            "enabled": ["search"],
        },
        "search": {
            "api_key": "",
            "engine": "duckduckgo",
        },
        "logging": {
            "level": "INFO",
            "format": "text",
            "file": "data/grok.log",
            "max_bytes": 10485760,
            "backup_count": 3,
        },
        "health": {
            "enabled": True,
            "port": 8080,
            "host": "0.0.0.0",
        },
    }


@pytest.fixture
def sample_config_file(tmp_path, sample_config):
    """Create a temporary config file."""
    import yaml

    config_file = tmp_path / "config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config, f)
    return config_file


@pytest.fixture
async def mock_db(mock_db_path):
    """Create a mock database."""
    from grok.db import Database

    db = Database(db_path=mock_db_path)
    await db.connect()
    yield db
    await db.close()


@pytest.fixture
def sample_mention():
    """Sample mention data."""
    return {
        "id": 12345678,
        "type": 1,
        "oid": 987654321,
        "root": 0,
        "parent": 0,
        "mid": 111111111,
        "uname": "测试用户",
        "content": "测试评论 @被提及用户",
        "ctime": 1700000000,
    }


@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""

    def _create_response(json_data: dict, status_code: int = 200):
        response = MagicMock()
        response.json.return_value = json_data
        response.raise_for_status = MagicMock()
        response.status_code = status_code
        return response

    return _create_response
