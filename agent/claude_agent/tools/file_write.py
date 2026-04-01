"""
File Write Tool
写入本地文件工具
"""
import os
from typing import Dict
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class FileWriteTool(BaseTool):
    """写入文件工具"""
    
    name = "write"
    description = (
        "Writes a file to the local filesystem. "
        "This tool will overwrite the existing file if there is one at the provided path. "
        "Prefer the edit tool for modifying existing files - it only sends the diff. "
        "Only use this tool to create new files or for complete rewrites. "
        "NEVER create documentation files (*.md) or README files unless explicitly "
        "requested by the User."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to write. Must be absolute.",
            },
        },
        "required": ["content", "file_path"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {
                "type": "boolean",
                "description": "Whether the write was successful",
            },
            "message": {
                "type": "string",
                "description": "Status message",
            },
            "file_path": {
                "type": "string",
                "description": "Path to the written file",
            },
            "bytes_written": {
                "type": "integer",
                "description": "Number of bytes written",
            },
        },
    }
    
    max_result_size_chars = 10_000
    is_concurrency_safe = False
    
    def is_read_only(self, input_params: Dict) -> bool:
        return False
    
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
        
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            return PermissionResult(
                behavior=PermissionBehavior.ASK,
                message=f"Directory {directory} does not exist. Need approval to create it.",
            )
        
        if os.path.exists(file_path):
            return PermissionResult(
                behavior=PermissionBehavior.ASK,
                message=f"File {file_path} already exists. Approval needed to overwrite.",
            )
        
        return PermissionResult(behavior=PermissionBehavior.ALLOW)
    
    async def execute(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> ToolResult:
        content = input_params["content"]
        file_path = input_params["file_path"]
        
        try:
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            with open(file_path, "w", encoding="utf-8") as f:
                bytes_written = f.write(content)
            
            return ToolResult(
                content=f"Successfully wrote file: {file_path}\nBytes: {bytes_written}\nLines: {len(content.splitlines())}",
                is_error=False,
                execution_time_ms=context.get_elapsed_ms(),
            )
        
        except Exception as e:
            return ToolResult(
                content=f"Error writing file {file_path}: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
