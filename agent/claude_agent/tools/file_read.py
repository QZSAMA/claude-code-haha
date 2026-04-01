"""
File Read Tool
读取本地文件工具
"""
import os
from typing import Dict, Optional
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class FileReadTool(BaseTool):
    """读取文件工具"""
    
    name = "read"
    description = (
        "Reads a file from the local filesystem. You can access any file directly by using this tool. "
        "Assume this tool can read all files on the machine. If the user provides a path to a file "
        "assume that path is valid. It is okay to read a file that does not exist; an error will be returned."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to read. Must be absolute, not relative.",
            },
            "offset": {
                "type": "integer",
                "description": "Starting line number (1-based), optional.",
                "minimum": 1,
            },
            "limit": {
                "type": "integer",
                "description": "Number of lines to read, optional.",
                "minimum": 1,
            },
        },
        "required": ["file_path"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "File content with line numbers",
            },
            "truncated": {
                "type": "boolean",
                "description": "Whether the output was truncated due to size limits",
            },
        },
    }
    
    max_result_size_chars = 200_000
    is_concurrency_safe = True
    default_max_lines = 2000
    
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
        file_path = input_params["file_path"]
        if not os.path.isabs(file_path):
            return PermissionResult(
                behavior=PermissionBehavior.DENY,
                message=f"File path must be absolute, got: {file_path}",
            )
        if not os.path.exists(file_path):
            return PermissionResult(
                behavior=PermissionBehavior.ALLOW,
                message="File does not exist, tool will report error",
            )
        if not os.path.isfile(file_path):
            return PermissionResult(
                behavior=PermissionBehavior.DENY,
                message=f"{file_path} is not a file, use ls for directories instead",
            )
        return PermissionResult(behavior=PermissionBehavior.ALLOW)
    
    async def execute(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> ToolResult:
        file_path = input_params["file_path"]
        offset = input_params.get("offset", 1)
        limit = input_params.get("limit", self.default_max_lines)
        
        try:
            if not os.path.exists(file_path):
                return ToolResult(
                    content=f"Error: File does not exist: {file_path}",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            if not os.path.isfile(file_path):
                return ToolResult(
                    content=f"Error: {file_path} is not a file",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            
            total_lines = len(lines)
            start_idx = offset - 1
            end_idx = start_idx + limit
            
            if start_idx >= total_lines:
                return ToolResult(
                    content=f"Error: offset {offset} exceeds total lines {total_lines}",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            selected_lines = lines[start_idx:end_idx]
            
            output_lines = []
            line_num_width = len(str(start_idx + len(selected_lines)))
            for i, line in enumerate(selected_lines, start=start_idx + 1):
                prefix = f"{i:>{line_num_width}}→"
                output_lines.append(f"{prefix}{line.rstrip()}")
            
            content = "\n".join(output_lines)
            truncated = len(lines) > end_idx
            
            if offset > 1 or truncated:
                header = f"File: {file_path} (lines {offset}-{start_idx + len(selected_lines)} of {total_lines})\n"
                if truncated:
                    header += "Output truncated - use offset and limit to read more\n"
                content = header + "\n" + content
            else:
                content = f"File: {file_path} ({total_lines} lines)\n\n" + content
            
            return ToolResult(
                content=content,
                is_error=False,
                execution_time_ms=context.get_elapsed_ms(),
            )
        
        except Exception as e:
            return ToolResult(
                content=f"Error reading file {file_path}: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
