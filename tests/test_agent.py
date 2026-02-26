"""Tests for agent module."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from grok.agent import AgentConfig, AgentError, BilibiliAgent


class TestAgentConfig:
    def test_default_values(self):
        config = AgentConfig()
        assert config.model == "openai/gpt-4o-mini"
        assert config.api_base == "https://api.openai.com/v1"
        assert config.api_key == ""
        assert config.max_tokens == 500
        assert config.temperature == 0.7

    def test_custom_values(self):
        config = AgentConfig(
            model="gpt-4",
            api_base="https://api.example.com/v1",
            api_key="test-key",
            max_tokens=1000,
            temperature=0.5,
            system_prompt="Custom prompt",
        )
        assert config.model == "gpt-4"
        assert config.api_base == "https://api.example.com/v1"
        assert config.api_key == "test-key"
        assert config.max_tokens == 1000
        assert config.temperature == 0.5
        assert config.system_prompt == "Custom prompt"


class TestBuildPrompt:
    def test_build_prompt_basic(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        prompt = agent._build_prompt("你好", "测试用户", None)

        assert "你好" in prompt
        assert "测试用户" in prompt
        assert "评论内容" in prompt

    def test_build_prompt_with_context(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        context = {
            "video_title": "测试视频标题",
            "video_description": "测试视频简介",
            "root_content": "根评论内容",
            "target_content": "目标评论内容",
        }

        prompt = agent._build_prompt("回复内容", "测试用户", context)

        assert "测试视频标题" in prompt
        assert "测试视频简介" in prompt
        assert "根评论内容" in prompt
        assert "目标评论内容" in prompt
        assert "回复内容" in prompt
        assert "测试用户" in prompt

    def test_build_prompt_with_partial_context(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        context = {
            "video_title": "测试视频标题",
        }

        prompt = agent._build_prompt("回复内容", "测试用户", context)

        assert "测试视频标题" in prompt
        assert "回复内容" in prompt


class TestCleanReply:
    def test_clean_reply_normal(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        result = agent._clean_reply("这是正常的回复")
        assert result == "这是正常的回复"

    def test_clean_reply_with_whitespace(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        result = agent._clean_reply("  带空格的回复  ")
        assert result == "带空格的回复"

    def test_clean_reply_json_block(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        result = agent._clean_reply('```json\n{"response": "测试回复"}\n```')
        assert "测试回复" in result

    def test_clean_reply_code_block(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        result = agent._clean_reply("```\n测试回复\n```")
        assert "测试回复" in result

    def test_clean_reply_truncate_long(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        long_reply = "a" * 250
        result = agent._clean_reply(long_reply)
        assert len(result) == 200
        assert result.endswith("...")

    def test_clean_reply_keep_short(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        short_reply = "短回复"
        result = agent._clean_reply(short_reply)
        assert result == "短回复"


@pytest.mark.asyncio
class TestGenerateReply:
    async def test_generate_reply_success(self, mock_agent_config):
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value={"messages": [MagicMock(content="测试回复")]})

        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent", return_value=mock_agent):
                agent = BilibiliAgent(config=mock_agent_config)

        result = await agent.generate_reply("你好", "测试用户")

        assert result == "测试回复"

    async def test_generate_reply_empty_messages(self, mock_agent_config):
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(return_value={"messages": []})

        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent", return_value=mock_agent):
                agent = BilibiliAgent(config=mock_agent_config)

        result = await agent.generate_reply("你好", "测试用户")

        assert result == "谢谢你的@！"

    async def test_generate_reply_timeout(self, mock_agent_config):
        async def slow_invoke(*args, **kwargs):
            await asyncio.sleep(2)
            return {"messages": [MagicMock(content="测试回复")]}

        mock_agent = AsyncMock()
        mock_agent.ainvoke = slow_invoke

        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent", return_value=mock_agent):
                agent = BilibiliAgent(config=mock_agent_config)

        with pytest.raises(AgentError, match="timed out"):
            await agent.generate_reply("你好", "测试用户", timeout=0.1)

    async def test_generate_reply_cancelled(self, mock_agent_config):
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(side_effect=asyncio.CancelledError())

        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent", return_value=mock_agent):
                agent = BilibiliAgent(config=mock_agent_config)

        with pytest.raises(AgentError, match="cancelled"):
            await agent.generate_reply("你好", "测试用户")

    async def test_generate_reply_with_context(self, mock_agent_config):
        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(
            return_value={"messages": [MagicMock(content="基于上下文的回复")]}
        )

        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent", return_value=mock_agent):
                agent = BilibiliAgent(config=mock_agent_config)

        context = {"video_title": "测试视频"}
        result = await agent.generate_reply("你好", "测试用户", context=context)

        assert result == "基于上下文的回复"


class TestToolManagement:
    def test_add_tool(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        from langchain_core.tools import BaseTool

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "test_tool"

        initial_count = len(agent.tools)

        with patch.object(agent, "_initialize_agent"):
            agent.add_tool(mock_tool)

        assert len(agent.tools) == initial_count + 1
        assert mock_tool in agent.tools

    def test_add_tool_no_duplicate(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        from langchain_core.tools import BaseTool

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "test_tool"

        with patch.object(agent, "_initialize_agent"):
            agent.add_tool(mock_tool)
            agent.add_tool(mock_tool)

        assert agent.tools.count(mock_tool) == 1

    def test_remove_tool(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        from langchain_core.tools import BaseTool

        mock_tool = MagicMock(spec=BaseTool)
        mock_tool.name = "test_tool"

        with patch.object(agent, "_initialize_agent"):
            agent.add_tool(mock_tool)
        assert mock_tool in agent.tools

        with patch.object(agent, "_initialize_agent"):
            agent.remove_tool("test_tool")
        assert mock_tool not in agent.tools

    def test_remove_nonexistent_tool(self, mock_agent_config):
        with patch("langchain_openai.ChatOpenAI"):
            with patch("grok.agent.create_react_agent"):
                agent = BilibiliAgent(config=mock_agent_config)

        initial_count = len(agent.tools)

        with patch.object(agent, "_initialize_agent"):
            agent.remove_tool("nonexistent_tool")

        assert len(agent.tools) == initial_count
