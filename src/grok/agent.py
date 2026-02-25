"""LangGraph AI Agent for generating replies."""

import json
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import create_react_agent


@dataclass
class AgentConfig:
    """Agent configuration."""

    model: str = "openai/gpt-4o-mini"
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    max_tokens: int = 500
    temperature: float = 0.7
    system_prompt: str = """You are a helpful assistant on Bilibili.
Respond naturally in Chinese to comments that @mention the user.
Keep your responses concise and friendly (under 200 characters).
Always be polite and helpful."""


class AgentError(Exception):
    """Agent error."""

    pass


class BilibiliAgent:
    """LangGraph-based AI agent for generating replies."""

    def __init__(
        self,
        config: AgentConfig,
        tools: list[BaseTool] | None = None,
    ):
        self.config = config
        self.tools = tools or []
        self._agent = None
        self._initialize_agent()

    def _initialize_agent(self) -> None:
        """Initialize the LangGraph agent."""
        # import logging

        # logging.getLogger("langgraph").setLevel(logging.DEBUG)
        # logging.getLogger("langchain").setLevel(logging.DEBUG)
        # logging.getLogger("langchain_openai").setLevel(logging.DEBUG)

        try:
            import litellm

            litellm.drop_params = True
            litellm.set_verbose = True
        except ImportError:
            pass

        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=self.config.model,
            base_url=self.config.api_base,
            api_key=self.config.api_key,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

        self._agent = create_react_agent(
            llm,
            tools=self.tools,
        )

    async def generate_reply(
        self,
        mention_content: str,
        username: str,
        context: dict | None = None,
        timeout: int = 60,
    ) -> str:
        """Generate a reply to a mention.

        Args:
            mention_content: The @mention comment content
            username: The username who mentioned
            context: Additional context (video title, etc.)
            timeout: Timeout in seconds

        Returns:
            Generated reply text
        """
        import asyncio
        import logging

        logger = logging.getLogger(__name__)

        prompt = self._build_prompt(mention_content, username, context)

        try:
            logger.info(f"Calling LLM for mention from {username}...")

            task = asyncio.create_task(
                self._agent.ainvoke(
                    {
                        "messages": [
                            SystemMessage(content=self.config.system_prompt),
                            HumanMessage(content=prompt),
                        ]
                    }
                )
            )

            try:
                result = await asyncio.wait_for(task, timeout=timeout)
            except asyncio.TimeoutError:
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass
                raise AgentError(f"LLM call timed out after {timeout} seconds")

            logger.info("LLM response received")

            messages = result.get("messages", [])
            if not messages:
                return "谢谢你的@！"

            last_message = messages[-1]
            reply = last_message.content

            return self._clean_reply(reply)

        except asyncio.CancelledError:
            logger.warning("LLM call cancelled")
            raise AgentError("LLM call cancelled")
        except Exception as e:
            raise AgentError(f"Failed to generate reply: {e}")

    def _build_prompt(
        self,
        mention_content: str,
        username: str,
        context: dict | None,
    ) -> str:
        """Build the prompt for the agent."""
        parts = [
            f"用户 @{username} 在B站评论中@提到了你。",
            f"评论内容: {mention_content}",
        ]

        if context:
            if "video_title" in context:
                parts.append(f"视频标题: {context['video_title']}")
            if "reply_count" in context:
                parts.append(f"评论回复数: {context['reply_count']}")

        parts.append("请生成一个简短友好的回复（不超过100字），表达感谢并适当回应。")

        return "\n".join(parts)

    def _clean_reply(self, reply: str) -> str:
        """Clean up the generated reply."""
        reply = reply.strip()

        if reply.startswith("```json"):
            try:
                data = json.loads(reply[7:])
                reply = data.get("response", reply)
            except json.JSONDecodeError:
                pass

        if reply.startswith("```"):
            lines = reply.split("\n")
            if len(lines) > 2:
                reply = "\n".join(lines[1:-1])
            reply = reply.strip("`")

        if len(reply) > 200:
            reply = reply[:197] + "..."

        return reply

    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to the agent."""
        if tool.name not in [t.name for t in self.tools]:
            self.tools.append(tool)
            self._initialize_agent()

    def remove_tool(self, tool_name: str) -> None:
        """Remove a tool from the agent."""
        self.tools = [t for t in self.tools if t.name != tool_name]
        self._initialize_agent()
