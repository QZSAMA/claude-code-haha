"""
Glob Tool
使用glob模式匹配文件路径
"""
import glob
import os
from typing import Dict, List
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class GlobTool(BaseTool):
    """Glob工具，按模式匹配文件"""
    
    name = "glob"
    description = (
        "Fast file pattern matching tool that works with any codebase size. "
        "Supports glob patterns like \"**/*.js\" or \"src/**/*.ts\". "
        "Returns matching file paths sorted by modification time. "
        "Use this tool when you need to find files by name patterns. "
        "When you are doing an open ended search that may require multiple rounds "
        "of globbing and grepping, use the Agent tool instead."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "The glob pattern to match files against",
            },
            "path": {
                "type": "string",
                "description": "The directory to search in. Defaults to current working directory",
            },
        },
        "required": ["pattern"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "matches": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of matching file paths",
            },
            "count": {
                "type": "integer",
                "description": "Number of matches found",
            },
        },
    }
    
    max_result_size_chars = 50_000
    is_concurrency_safe = True
    max_matches = 1000
    
    def __init__(self, working_directory: str = "."):
        super().__init__()
        self.working_directory = working_directory
    
    def is_read_only(self, input_params: Dict) -> bool:
        return True
    
    async def check_permissions(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> PermissionResult:
        return PermissionResult(behavior=PermissionBehavior.ALLOW)
    
    def _get_matching_files(self, pattern: str, search_path: str) -> List[str]:
        """获取匹配文件"""
        if os.path.isabs(pattern):
            full_pattern = pattern
        else:
            full_pattern = os.path.join(search_path, pattern)
        
        matches = []
        for path in glob.glob(full_pattern, recursive=True):
            if os.path.isfile(path):
                matches.append(path)
        
        matches.sort(key=lambda p: -os.path.getmtime(p))
        
        if len(matches) > self.max_matches:
            matches = matches[:self.max_matches]
        
        return matches
    
    async def execute(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> ToolResult:
        pattern = input_params["pattern"]
        search_path = input_params.get("path", context.working_directory)
        
        try:
            if not os.path.exists(search_path):
                return ToolResult(
                    content=f"Error: Search path does not exist: {search_path}",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            if not os.path.isdir(search_path):
                return ToolResult(
                    content=f"Error: {search_path} is not a directory",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            matches = self._get_matching_files(pattern, search_path)
            
            if not matches:
                return ToolResult(
                    content=f"No matches found for pattern: {pattern}",
                    is_error=False,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            output_lines = [f"Found {len(matches)} matches:"]
            for match in matches:
                output_lines.append(f"- {match}")
            
            if len(matches) == self.max_matches:
                output_lines.append(f"\n(Results truncated after {self.max_matches} matches)")
            
            content = "\n".join(output_lines)
            return ToolResult(
                content=content,
                is_error=False,
                execution_time_ms=context.get_elapsed_ms(),
            )
        
        except Exception as e:
            return ToolResult(
                content=f"Error searching with glob: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
