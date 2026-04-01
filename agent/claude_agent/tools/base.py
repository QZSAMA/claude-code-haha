"""
Base Tool Definition
工具基类定义，所有具体工具都继承自此类
"""
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Callable, Dict, Optional, Tuple
from pydantic import BaseModel, ValidationError
from claude_agent.state import PermissionResult, PermissionBehavior


class ToolContext:
    """
    Tool execution context
    传递给工具执行的上下文，包含运行时信息和回调
    """
    def __init__(
        self,
        working_directory: str,
        abort_signal: Optional[asyncio.Event] = None,
        on_progress: Optional[Callable[[str], None]] = None,
    ):
        self.working_directory = working_directory
        self.abort_signal = abort_signal or asyncio.Event()
        self.on_progress = on_progress
        self.start_time = time.time()
    
    def is_aborted(self) -> bool:
        """检查是否已中止"""
        return self.abort_signal.is_set()
    
    def send_progress(self, message: str) -> None:
        """发送进度更新"""
        if self.on_progress:
            self.on_progress(message)
    
    def get_elapsed_ms(self) -> int:
        """获取已执行时间毫秒"""
        return int((time.time() - self.start_time) * 1000)


class ToolResult:
    """
    Tool execution result
    工具执行结果封装
    """
    def __init__(
        self,
        content: str,
        is_error: bool = False,
        execution_time_ms: Optional[int] = None,
    ):
        self.content = content
        self.is_error = is_error
        self.execution_time_ms = execution_time_ms
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "is_error": self.is_error,
            "execution_time_ms": self.execution_time_ms,
        }


class BaseTool(ABC):
    """
    Base Tool Abstract Base Class
    所有工具必须继承此类，实现必要的方法
    """
    
    name: str
    """工具名称，用于函数调用匹配"""
    
    description: str
    """工具描述，显示给模型"""
    
    input_schema: Dict[str, Any]
    """输入JSON Schema，描述参数结构"""
    
    output_schema: Dict[str, Any]
    """输出JSON Schema，描述返回结构"""
    
    max_result_size_chars: int = 100_000
    """最大结果字符数，超限会持久化到磁盘"""
    
    is_concurrency_safe: bool = False
    """是否并发安全，如果工具修改文件系统则一般不是并发安全"""
    
    def __init__(self):
        pass
    
    @abstractmethod
    async def check_permissions(
        self,
        input_params: Dict[str, Any],
        context: ToolContext,
    ) -> PermissionResult:
        """
        检查工具调用权限
        工具可以进行自定义权限检查
        
        Returns:
            PermissionResult 包含behavior(allow/deny/ask)和message
        """
        return PermissionResult(behavior=PermissionBehavior.ALLOW)
    
    def is_read_only(self, input_params: Dict[str, Any]) -> bool:
        """
        工具调用是否只读，不修改文件系统
        用于并发安全判断，如果只读则可以并发执行
        
        Default implementation returns False, override if needed.
        """
        return False
    
    @abstractmethod
    async def execute(
        self,
        input_params: Dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        """
        Execute the tool with given input parameters
        执行工具，返回结果
        
        Args:
            input_params: 验证后的输入参数
            context: 执行上下文
        
        Returns:
            ToolResult 执行结果
        """
        pass
    
    def validate_input(self, input_params: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate input parameters against input schema
        默认实现使用pydantic验证，可覆盖
        
        Returns:
            (is_valid, error_message)
        """
        try:
            schema_model = self._create_schema_model()
            schema_model(**input_params)
            return True, ""
        except ValidationError as e:
            return False, str(e)
    
    def _create_schema_model(self) -> BaseModel:
        """从input_schema动态创建pydantic模型"""
        from pydantic import create_model
        fields = {}
        for name, defn in self.input_schema.get("properties", {}).items():
            required = name in self.input_schema.get("required", [])
            if defn.get("type") == "string":
                fields[name] = (str, ... if required else None)
            elif defn.get("type") == "integer":
                fields[name] = (int, ... if required else None)
            elif defn.get("type") == "number":
                fields[name] = (float, ... if required else None)
            elif defn.get("type") == "boolean":
                fields[name] = (bool, ... if required else None)
            elif defn.get("type") == "array":
                fields[name] = (list, ... if required else None)
            elif defn.get("type") == "object":
                fields[name] = (dict, ... if required else None)
            else:
                fields[name] = (Any, ... if required else None)
        return create_model("ToolInputSchema", **fields)
    
    def get_description_for_prompt(self) -> str:
        """获取用于system prompt的工具描述"""
        lines = [f"## {self.name}"]
        lines.append(self.description)
        lines.append("")
        lines.append("Parameters:")
        for name, prop in self.input_schema.get("properties", {}).items():
            required = "required" in self.input_schema.get("required", []) and name in self.input_schema["required"]
            desc = prop.get("description", "")
            type_name = prop.get("type", "any")
            req_mark = "(required)" if required else "(optional)"
            lines.append(f"- {name}: {type_name} {req_mark} - {desc}")
        lines.append("")
        return "\n".join(lines)


def build_tool(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
    output_schema: Dict[str, Any],
    execute_func: Callable[[Dict[str, Any], ToolContext], ToolResult],
    check_permissions_func: Optional[Callable] = None,
    is_concurrency_safe: bool = False,
    max_result_size_chars: int = 100_000,
) -> BaseTool:
    """
    Builder pattern for creating tools from functions
    便捷构建工具实例
    """
    class BuiltTool(BaseTool):
        def __init__(self):
            self.name = name
            self.description = description
            self.input_schema = input_schema
            self.output_schema = output_schema
            self.is_concurrency_safe = is_concurrency_safe
            self.max_result_size_chars = max_result_size_chars
            super().__init__()
        
        async def check_permissions(self, input_params, context):
            if check_permissions_func:
                return check_permissions_func(input_params, context)
            return PermissionResult(behavior=PermissionBehavior.ALLOW)
        
        async def execute(self, input_params, context):
            return await execute_func(input_params, context)
    
    return BuiltTool()
