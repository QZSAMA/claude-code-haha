"""
LS Tool
列出目录内容工具
"""
import os
from typing import Dict, List
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class LsTool(BaseTool):
    """列出目录内容工具"""
    
    name = "ls"
    description = (
        "Lists files and directories in a given path. "
        "Supports glob patterns for ignoring files."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute path to the directory to list",
            },
            "ignore": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of glob patterns to ignore, optional",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "directories": {
                "type": "array",
                "items": {"type": "string"},
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }
    
    max_result_size_chars = 50_000
    is_concurrency_safe = True
    
    def is_read_only(self, input_params: Dict) -> bool:
        return True
    
    async def check_permissions(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> PermissionResult:
        return PermissionResult(behavior=PermissionBehavior.ALLOW)
    
    def _match_ignore(self, name: str, ignore_patterns: List[str]) -> bool:
        """检查是否应该忽略"""
        import fnmatch
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(name, pattern):
                return True
        return False
    
    async def execute(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> ToolResult:
        path = input_params["path"]
        ignore = input_params.get("ignore", [])
        
        try:
            if not os.path.exists(path):
                return ToolResult(
                    content=f"Error: Path does not exist: {path}",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            if not os.path.isdir(path):
                return ToolResult(
                    content=f"Error: {path} is not a directory",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            entries = os.listdir(path)
            dirs = []
            files = []
            
            for entry in entries:
                if self._match_ignore(entry, ignore):
                    continue
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    dirs.append(entry + "/")
                else:
                    files.append(entry)
            
            dirs.sort()
            files.sort()
            
            output_lines = [f"Directory: {path}"]
            output_lines.append("")
            
            if dirs:
                output_lines.append("Directories:")
                for d in dirs:
                    output_lines.append(f"  {d}")
                output_lines.append("")
            
            if files:
                output_lines.append("Files:")
                for f in files:
                    output_lines.append(f"  {f}")
            
            if not dirs and not files:
                output_lines.append("(empty directory)")
            
            content = "\n".join(output_lines)
            return ToolResult(
                content=content,
                is_error=False,
                execution_time_ms=context.get_elapsed_ms(),
            )
        
        except Exception as e:
            return ToolResult(
                content=f"Error listing directory {path}: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
