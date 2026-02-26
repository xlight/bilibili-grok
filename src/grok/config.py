"""Configuration management."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BilibiliConfig:
    """BiliBili-specific config."""

    credential_path: str = "data/credentials.json"


@dataclass
class MonitorConfig:
    """Mention monitor config."""

    poll_interval: int = 60
    batch_size: int = 20
    processing_interval_seconds: int = 20
    processing_timeout_minutes: int = 20


@dataclass
class ReplyConfig:
    """Reply config."""

    rate_limit_seconds: int = 3
    max_retries: int = 3


@dataclass
class AgentConfig:
    """AI Agent config."""

    model: str = "openai/gpt-4o-mini"
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    max_tokens: int = 500
    temperature: float = 0.7
    system_prompt: str = field(
        default="""You are a helpful assistant on Bilibili.
Respond naturally in Chinese to comments that @mention the user.
Keep your responses concise and friendly."""
    )


@dataclass
class ToolsConfig:
    """Tools config."""

    enabled: list[str] = field(default_factory=lambda: ["search"])


@dataclass
class SearchConfig:
    """Search tool config."""

    api_key: str = ""
    engine: str = "duckduckgo"


@dataclass
class LoggingConfig:
    """Logging config."""

    level: str = "INFO"
    format: str = "text"
    file: str = "data/grok.log"
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 3


@dataclass
class HealthConfig:
    """Health check config."""

    enabled: bool = True
    port: int = 8080
    host: str = "0.0.0.0"


@dataclass
class Config:
    """Main configuration."""

    bilibili: BilibiliConfig = field(default_factory=BilibiliConfig)
    monitor: MonitorConfig = field(default_factory=MonitorConfig)
    reply: ReplyConfig = field(default_factory=ReplyConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    health: HealthConfig = field(default_factory=HealthConfig)


class ConfigError(Exception):
    """Configuration error."""

    pass


def _apply_env_overrides(config: dict, prefix: str = "GROK_") -> None:
    """Apply environment variable overrides to config.

    Environment variables should be named like GROK_xxx_yyy for nested keys.
    Example: GROK_AGENT_MODEL=gpt-4 -> config["agent"]["model"] = "gpt-4"

    For keys with underscores, the function will try to match existing keys first.
    Example: GROK_MONITOR_POLL_INTERVAL=30 -> config["monitor"]["poll_interval"] = 30
    """

    def _find_and_set_key(current: dict, parts: list[str], value: Any) -> bool:
        """Try to find and set a key by combining parts. Returns True if found."""
        if not parts:
            return False

        # Try to match by combining parts (greedy, longest first)
        for i in range(len(parts), 0, -1):
            combined = "_".join(parts[:i])
            if combined in current:
                if i == len(parts):
                    # Found the complete match
                    current[combined] = value
                    return True
                else:
                    # Found partial match, recurse
                    if isinstance(current[combined], dict):
                        return _find_and_set_key(current[combined], parts[i:], value)
                    return False

        # No match found, create nested structure
        if len(parts) == 1:
            current[parts[0]] = value
            return True

        if parts[0] not in current:
            current[parts[0]] = {}
        return _find_and_set_key(current[parts[0]], parts[1:], value)

    for key, value in os.environ.items():
        if not key.startswith(prefix):
            continue

        parts = key[len(prefix) :].lower().split("_")
        _find_and_set_key(config, parts, _parse_env_value(value))


def _parse_env_value(value: str) -> Any:
    """Parse environment variable value."""
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    if value.isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        pass

    if value.startswith("[") and value.endswith("]"):
        try:
            import ast

            return ast.literal_eval(value)
        except ValueError:
            pass

    return value


def load_config(config_path: str = "config.yaml") -> Config:
    """Load configuration from YAML file with env overrides."""
    config_file = Path(config_path)

    if not config_file.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    with open(config_file) as f:
        config_dict = yaml.safe_load(f)

    _apply_env_overrides(config_dict)

    bilibili_cfg = BilibiliConfig(**config_dict.get("bilibili", {}))
    monitor_cfg = MonitorConfig(**config_dict.get("monitor", {}))
    reply_cfg = ReplyConfig(**config_dict.get("reply", {}))
    agent_cfg = AgentConfig(**config_dict.get("agent", {}))
    tools_cfg = ToolsConfig(**config_dict.get("tools", {}))
    search_cfg = SearchConfig(**config_dict.get("search", {}))
    logging_cfg = LoggingConfig(**config_dict.get("logging", {}))
    health_cfg = HealthConfig(**config_dict.get("health", {}))

    return Config(
        bilibili=bilibili_cfg,
        monitor=monitor_cfg,
        reply=reply_cfg,
        agent=agent_cfg,
        tools=tools_cfg,
        search=search_cfg,
        logging=logging_cfg,
        health=health_cfg,
    )


def validate_config(config: Config) -> None:
    """Validate configuration."""
    if not config.agent.api_key:
        raise ConfigError("agent.api_key is required")

    if config.health.enabled and config.health.port <= 0:
        raise ConfigError("health.port must be positive")

    if config.monitor.poll_interval < 10:
        raise ConfigError("monitor.poll_interval must be at least 10 seconds")

    if config.reply.rate_limit_seconds < 1:
        raise ConfigError("reply.rate_limit_seconds must be at least 1")

    if config.monitor.processing_interval_seconds < 1:
        raise ConfigError("monitor.processing_interval_seconds must be at least 1")

    if config.monitor.processing_timeout_minutes < 1:
        raise ConfigError("monitor.processing_timeout_minutes must be at least 1")
