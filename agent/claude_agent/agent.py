"""
Main Claude Agent
主Claude Agent类，提供高层API
"""
import os
import uuid
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional
from langgraph.graph import StateGraph
from claude_agent.state import AgentState, AgentConfig, ConversationTurn
from claude_agent.tools import ToolRegistry, create_default_registry
from claude_agent.nodes import ClaudeAPIClient
from claude_agent.graph import create_compiled_agent


class ClaudeAgent:
    """
    Claude Agent - 基于LangGraph重构的Claude CLI Agent
    
    完整复刻原始Claude CLI的所有功能:
    - 工具调用系统
    - 自动上下文压缩
    - 流式响应
    - 权限检查
    - 多轮对话管理
    """
    
    def __init__(
        self,
        config: Optional[AgentConfig] = None,
        tool_registry: Optional[ToolRegistry] = None,
        api_key: Optional[str] = None,
        api_base_url: Optional[str] = None,
        working_directory: Optional[str] = None,
    ):
        """
        初始化Claude Agent
        
        Args:
            config: Agent配置，如果为None使用默认配置
            tool_registry: 工具注册表，如果为None创建默认注册表
            api_key: Anthropic API key，如果为None从环境变量读取
            api_base_url: 可选的API base URL
            working_directory: 工作目录，如果为None使用当前目录
        """
        self.config = config or AgentConfig()
        
        self.working_directory = working_directory or os.getcwd()
        self.config.working_directory = self.working_directory
        
        self.tool_registry = tool_registry or create_default_registry(self.working_directory)
        
        self.api_client = ClaudeAPIClient(
            api_key=api_key,
            base_url=api_base_url,
        )
        
        self._graph_config = {
            "tool_registry": self.tool_registry,
            "api_client": self.api_client,
            "agent_config": self.config,
            "working_directory": self.working_directory,
        }
        
        self._compiled_agent = create_compiled_agent(self._graph_config)
        
        self.current_state: Optional[AgentState] = None
    
    def get_initial_state(self, user_input: str) -> AgentState:
        """
        获取初始状态，开始新对话
        
        Args:
            user_input: 用户初始输入
        
        Returns:
            初始化后的AgentState
        """
        turn_id = str(uuid.uuid4())
        current_turn = ConversationTurn(
            turn_id=turn_id,
            user_input=user_input,
        )
        
        user_message = {
            "role": "user",
            "content": user_input,
        }
        
        state = AgentState(
            messages=[user_message],
            user_input=user_input,
            current_turn=current_turn,
            is_first_turn=True,
            should_continue=True,
            model=self.config.model,
            working_directory=self.working_directory,
            additional_working_directories=self.config.additional_working_directories,
        )
        
        state.update_timestamp()
        
        return state
    
    def add_user_message(self, state: AgentState, user_input: str) -> AgentState:
        """
        添加用户消息到现有对话
        
        Args:
            state: 当前状态
            user_input: 用户新输入
        
        Returns:
            更新后的状态
        """
        turn_id = str(uuid.uuid4())
        current_turn = ConversationTurn(
            turn_id=turn_id,
            user_input=user_input,
        )
        
        user_message = {
            "role": "user",
            "content": user_input,
        }
        
        new_messages = list(state.messages)
        new_messages.append(user_message)
        
        new_state = state.model_copy(deep=True)
        new_state.messages = new_messages
        new_state.user_input = user_input
        new_state.current_turn = current_turn
        new_state.conversation_turns.append(current_turn)
        new_state.is_first_turn = False
        new_state.should_continue = True
        new_state.update_timestamp()
        
        return new_state
    
    async def run(
        self,
        state: AgentState,
    ) -> AgentState:
        """
        同步运行agent直到完成
        
        Args:
            state: 当前Agent状态
        
        Returns:
            最终Agent状态
        """
        result = await self._compiled_agent.ainvoke(state)
        return AgentState(**result)
    
    async def stream(
        self,
        state: AgentState,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        流式运行agent，逐步输出更新
        
        Args:
            state: 当前Agent状态
        
        Yields:
            状态更新字典
        """
        async for chunk in self._compiled_agent.astream(state):
            yield chunk
    
    def register_tool(self, tool) -> None:
        """
        注册自定义工具
        
        Args:
            tool: BaseTool实例
        """
        self.tool_registry.register(tool)
    
    def get_final_response(self, state: AgentState) -> str:
        """
        从状态提取最终助理响应
        
        Args:
            state: Agent状态
        
        Returns:
            响应文本
        """
        if not state.messages:
            return ""
        
        for msg in reversed(state.messages):
            if msg.get("role") == "assistant":
                content = msg.get("content", "")
                if isinstance(content, str):
                    return content
                elif isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if block.get("type") == "text":
                            text_parts.append(block.get("text", ""))
                    return "".join(text_parts)
        
        return ""
    
    def get_token_usage(self, state: AgentState) -> Dict[str, int]:
        """获取token使用统计"""
        return state.token_usage
    
    def get_estimated_total_tokens(self, state: AgentState) -> int:
        """获取估计总token数"""
        return state.estimated_tokens


def create_agent(
    model: str = "claude-3-5-sonnet-20241022",
    max_tokens: int = 200000,
    max_output_tokens: int = 4096,
    working_directory: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ClaudeAgent:
    """
    便捷工厂函数创建Claude Agent
    
    Args:
        model: 模型名称
        max_tokens: 最大上下文token
        max_output_tokens: 最大输出token
        working_directory: 工作目录
        api_key: API key
    
    Returns:
        配置好的ClaudeAgent实例
    """
    config = AgentConfig(
        model=model,
        max_tokens=max_tokens,
        max_output_tokens=max_output_tokens,
    )
    
    return ClaudeAgent(
        config=config,
        working_directory=working_directory,
        api_key=api_key,
    )
