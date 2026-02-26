"""Tests for config module."""

import os

import pytest

from grok.config import (
    AgentConfig,
    BilibiliConfig,
    Config,
    ConfigError,
    MonitorConfig,
    ReplyConfig,
    _apply_env_overrides,
    load_config,
    validate_config,
)


class TestBilibiliConfig:
    def test_default_values(self):
        config = BilibiliConfig()
        assert config.credential_path == "data/credentials.json"

    def test_custom_values(self):
        config = BilibiliConfig(credential_path="/custom/path.json")
        assert config.credential_path == "/custom/path.json"


class TestMonitorConfig:
    def test_default_values(self):
        config = MonitorConfig()
        assert config.poll_interval == 60
        assert config.batch_size == 20

    def test_custom_values(self):
        config = MonitorConfig(poll_interval=30, batch_size=10)
        assert config.poll_interval == 30
        assert config.batch_size == 10


class TestAgentConfig:
    def test_default_values(self):
        config = AgentConfig()
        assert config.model == "openai/gpt-4o-mini"
        assert config.max_tokens == 500
        assert config.temperature == 0.7

    def test_custom_values(self):
        config = AgentConfig(
            model="gpt-4",
            api_key="test-key",
            temperature=0.5,
        )
        assert config.model == "gpt-4"
        assert config.api_key == "test-key"
        assert config.temperature == 0.5


class TestLoadConfig:
    def test_load_from_file(self, sample_config_file):
        config = load_config(str(sample_config_file))

        assert isinstance(config, Config)
        assert config.bilibili.credential_path == "data/credentials.json"
        assert config.monitor.poll_interval == 60
        assert config.agent.api_key == "test-api-key"

    def test_file_not_found(self):
        with pytest.raises(ConfigError, match="not found"):
            load_config("nonexistent.yaml")

    def test_env_overrides(self, sample_config_file):
        os.environ["GROK_MONITOR_POLL_INTERVAL"] = "120"
        os.environ["GROK_AGENT_MODEL"] = "gpt-4"

        try:
            config = load_config(str(sample_config_file))
            assert config.monitor.poll_interval == 120
            assert config.agent.model == "gpt-4"
        finally:
            del os.environ["GROK_MONITOR_POLL_INTERVAL"]
            del os.environ["GROK_AGENT_MODEL"]


class TestValidateConfig:
    def test_valid_config(self, sample_config):
        config = Config(
            bilibili=BilibiliConfig(),
            monitor=MonitorConfig(),
            reply=ReplyConfig(),
            agent=AgentConfig(api_key="test-key"),
        )

        validate_config(config)

    def test_missing_api_key(self):
        config = Config(
            bilibili=BilibiliConfig(),
            monitor=MonitorConfig(),
            reply=ReplyConfig(),
            agent=AgentConfig(api_key=""),
        )

        with pytest.raises(ConfigError, match="api_key is required"):
            validate_config(config)

    def test_invalid_poll_interval(self):
        config = Config(
            bilibili=BilibiliConfig(),
            monitor=MonitorConfig(poll_interval=5),
            reply=ReplyConfig(),
            agent=AgentConfig(api_key="test-key"),
        )

        with pytest.raises(ConfigError, match="poll_interval must be at least"):
            validate_config(config)


class TestApplyEnvOverrides:
    def test_string_override(self):
        config = {"agent": {"model": "default"}}
        os.environ["GROK_AGENT_MODEL"] = "custom-model"

        try:
            _apply_env_overrides(config)
            assert config["agent"]["model"] == "custom-model"
        finally:
            del os.environ["GROK_AGENT_MODEL"]

    def test_int_override(self):
        config = {"monitor": {"poll_interval": 60}}
        os.environ["GROK_MONITOR_POLL_INTERVAL"] = "30"

        try:
            _apply_env_overrides(config)
            assert config["monitor"]["poll_interval"] == 30
        finally:
            del os.environ["GROK_MONITOR_POLL_INTERVAL"]

    def test_bool_override(self):
        config = {"health": {"enabled": False}}
        os.environ["GROK_HEALTH_ENABLED"] = "true"

        try:
            _apply_env_overrides(config)
            assert config["health"]["enabled"] is True
        finally:
            del os.environ["GROK_HEALTH_ENABLED"]

    def test_list_override(self):
        config = {"tools": {"enabled": ["search"]}}
        os.environ["GROK_TOOLS_ENABLED"] = '["search", "calculator"]'

        try:
            _apply_env_overrides(config)
            assert config["tools"]["enabled"] == ["search", "calculator"]
        finally:
            del os.environ["GROK_TOOLS_ENABLED"]
