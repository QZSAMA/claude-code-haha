"""
Tools Module
工具模块导出核心工具类和注册表
"""
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult, build_tool
from claude_agent.tools.file_read import FileReadTool
from claude_agent.tools.file_write import FileWriteTool
from claude_agent.tools.file_edit import FileEditTool
from claude_agent.tools.glob import GlobTool
from claude_agent.tools.grep import GrepTool
from claude_agent.tools.ls import LsTool
from claude_agent.tools.bash import BashTool
from claude_agent.tools.todo_write import TodoWriteTool
from claude_agent.tools.web_search import WebSearchTool
from claude_agent.tools.web_fetch import WebFetchTool


__all__ = [
    "BaseTool",
    "ToolContext",
    "ToolResult",
    "build_tool",
    "FileReadTool",
    "FileWriteTool",
    "FileEditTool",
    "GlobTool",
    "GrepTool",
    "LsTool",
    "BashTool",
    "TodoWriteTool",
    "WebSearchTool",
    "WebFetchTool",
]


class ToolRegistry:
    """工具注册表，管理所有可用工具"""
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
    
    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        self._tools[tool.name] = tool
    
    def get_tool(self, name: str) -> BaseTool | None:
        """按名称获取工具"""
        return self._tools.get(name)
    
    def list_tools(self) -> list[BaseTool]:
        """列出所有工具"""
        return list(self._tools.values())
    
    def get_tool_names(self) -> list[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())
    
    def get_openai_functions(self) -> list[dict]:
        """获取OpenAI函数格式定义"""
        functions = []
        for tool in self._tools.values():
            functions.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
            })
        return functions
    
    def get_anthropic_tools(self) -> list[dict]:
        """获取Anthropic工具格式定义"""
        tools = []
        for tool in self._tools.values():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            })
        return tools
    
    def get_system_prompt_tools_section(self) -> str:
        """生成system prompt中的工具描述部分"""
        lines = ["## Available Tools\n"]
        lines.append("You have access to the following tools:\n")
        for tool in sorted(self._tools.values(), key=lambda t: t.name):
            lines.append(tool.get_description_for_prompt())
        lines.append("\nWhen you need to use a tool, you MUST use the XML format specified.")
        return "\n".join(lines)


def create_default_registry(working_directory: str = ".") -> ToolRegistry:
    """创建默认工具注册表，包含所有核心工具"""
    registry = ToolRegistry()
    
    registry.register(FileReadTool(working_directory))
    registry.register(FileWriteTool())
    registry.register(FileEditTool())
    registry.register(GlobTool(working_directory))
    registry.register(GrepTool())
    registry.register(LsTool())
    registry.register(BashTool())
    registry.register(TodoWriteTool())
    
    try:
        registry.register(WebSearchTool())
        registry.register(WebFetchTool())
    except Exception:
        pass
    
    return registry
