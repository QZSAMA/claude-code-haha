"""
Agent State Definition
定义Agent的完整状态结构，遵循LangGraph设计模式
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from typing_extensions import Annotated


class MessageRole(str, Enum):
    """消息角色枚举"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    COMPACT_BOUNDARY = "compact_boundary"
    COMPACT_SUMMARY = "compact_summary"


class ContentBlockType(str, Enum):
    """内容块类型"""
    TEXT = "text"
    TOOL_USE = "tool_use"


class ToolCall(BaseModel):
    """工具调用"""
    id: str
    name: str
    input: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


class ContentBlock(BaseModel):
    """消息内容块"""
    type: ContentBlockType
    text: Optional[str] = None
    tool_use: Optional[ToolCall] = None


class ToolResult(BaseModel):
    """工具调用结果"""
    tool_use_id: str
    content: str
    is_error: bool = False
    execution_time_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationTurn(BaseModel):
    """对话回合，表示对话的一个回合"""
    turn_id: str
    user_input: str
    timestamp: datetime = Field(default_factory=datetime.now)
    assistant_response: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_results: List[ToolResult] = Field(default_factory=list)
    is_completed: bool = False
    tokens_used: int = 0


class PermissionBehavior(str, Enum):
    """权限行为枚举"""
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionResult(BaseModel):
    """权限检查结果"""
    behavior: PermissionBehavior
    message: str = ""


class AgentState(BaseModel):
    """
    Agent 完整状态定义
    包含所有对话上下文和运行时状态

    遵循LangGraph状态设计模式
    """
    messages: Annotated[List[Dict[str, Any]], add_messages] = Field(default_factory=list)
    
    messages_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    current_turn: Optional[ConversationTurn] = None
    
    conversation_turns: List[ConversationTurn] = Field(default_factory=list)
    
    user_input: str = ""
    
    is_first_turn: bool = True
    
    should_continue: bool = True
    
    stop_reason: Optional[str] = None
    
    recovery_count: int = 0
    
    max_recovery: int = 3
    
    token_usage: Dict[str, int] = Field(default_factory=dict)
    
    estimated_tokens: int = 0
    
    needs_compaction: bool = False
    
    is_compacting: bool = False
    
    compacted_history: Optional[str] = None
    
    tools_to_execute: List[ToolCall] = Field(default_factory=list)
    
    current_tool_result: Optional[ToolResult] = None
    
    executing_tools: bool = False
    
    available_tools: List[str] = Field(default_factory=list)
    
    permission_request: Optional[Dict[str, Any]] = None
    
    waiting_for_user: bool = False
    
    user_response: Optional[str] = None
    
    model: str = "claude-3-sonnet-20240229"
    
    system_prompt: str = ""
    
    working_directory: str = ""
    
    additional_working_directories: List[str] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.now)
    
    updated_at: datetime = Field(default_factory=datetime.now)
    
    def update_timestamp(self) -> None:
        """更新时间戳"""
        self.updated_at = datetime.now()
    
    def add_tool_call(self, tool_call: ToolCall) -> None:
        """添加工具调用"""
        if self.current_turn:
            self.current_turn.tool_calls.append(tool_call)
        self.tools_to_execute.append(tool_call)
    
    def add_tool_result(self, result: ToolResult) -> None:
        """添加工具结果"""
        if self.current_turn:
            self.current_turn.tool_results.append(result)
    
    def get_total_tokens(self) -> int:
        """获取总token使用量"""
        return sum(self.token_usage.values())
    
    def needs_compaction_check(self, max_tokens: int, compact_threshold: float = 0.8) -> bool:
        """检查是否需要压缩"""
        if self.estimated_tokens > max_tokens * compact_threshold:
            self.needs_compaction = True
            return True
        return False
    
    def to_anthropic_messages(self) -> List[Dict[str, Any]]:
        """转换为Anthropic API要求的消息格式"""
        result = []
        for msg in self.messages:
            result.append(msg)
        return result


class AgentConfig(BaseModel):
    """Agent配置"""
    model: str = "claude-3-sonnet-20240229"
    max_tokens: int = 100000
    max_output_tokens: int = 4096
    max_recovery_attempts: int = 3
    auto_compact_enabled: bool = True
    auto_compact_threshold: float = 0.8
    max_output_tokens_for_summary: int = 20000
    temperature: float = 0.0
    top_p: float = 1.0
    streaming_enabled: bool = True
    stream_tool_execution: bool = True
    working_directory: str = "."
    additional_working_directories: List[str] = Field(default_factory=list)
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    
    def to_api_params(self) -> Dict[str, Any]:
        """转换为API参数字典"""
        return {
            "model": self.model,
            "max_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "stream": self.streaming_enabled,
        }
