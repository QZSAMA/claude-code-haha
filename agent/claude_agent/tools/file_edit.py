"""
File Edit Tool
精确搜索替换编辑文件工具
"""
import os
import re
from typing import Dict, Optional
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class FileEditTool(BaseTool):
    """精确编辑文件工具"""
    
    name = "edit"
    description = (
        "Performs exact string replacements in files. "
        "When editing text from Read tool output, ensure you preserve the exact indentation. "
        "NEVER include any part of the line number prefix in the old_string or new_string. "
        "ALWAYS prefer editing existing files in the codebase. NEVER create new files unless explicitly required. "
        "The edit will FAIL if old_string is not unique or doesn't match exactly."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "The absolute path to the file to edit",
            },
            "old_string": {
                "type": "string",
                "description": "The exact content to search for (case-sensitive)",
            },
            "new_string": {
                "type": "string",
                "description": "The new content to replace old_string with",
            },
            "replace_all": {
                "type": "boolean",
                "description": "Replace all occurrences instead of just the first. Default: false",
                "default": False,
            },
        },
        "required": ["file_path", "old_string", "new_string"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "replacements_made": {"type": "integer"},
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
        if not os.path.exists(file_path):
            return PermissionResult(
                behavior=PermissionBehavior.DENY,
                message=f"File does not exist: {file_path}, use write to create new files",
            )
        if not os.path.isfile(file_path):
            return PermissionResult(
                behavior=PermissionBehavior.DENY,
                message=f"{file_path} is not a file",
            )
        return PermissionResult(behavior=PermissionBehavior.ALLOW)
    
    async def execute(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> ToolResult:
        file_path = input_params["file_path"]
        old_string = input_params["old_string"]
        new_string = input_params["new_string"]
        replace_all = input_params.get("replace_all", False)
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            if old_string not in content:
                similarity = self._fuzzy_match(content, old_string)
                return ToolResult(
                    content=f"Error: old_string not found in {file_path}. "
                           f"Did you include the exact whitespace and indentation? "
                           f"Best match similarity: {similarity:.1%}",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            occurrences = self._count_occurrences(content, old_string)
            if occurrences > 1 and not replace_all:
                return ToolResult(
                    content=f"Error: Found {occurrences} occurrences of old_string in {file_path}. "
                           f"Use replace_all=true to replace all occurrences or make old_string more specific.",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replacements_made = occurrences
            else:
                new_content = content.replace(old_string, new_string, 1)
                replacements_made = 1
            
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            
            return ToolResult(
                content=f"Successfully edited {file_path}: {replacements_made} replacement(s) made",
                is_error=False,
                execution_time_ms=context.get_elapsed_ms(),
            )
        
        except Exception as e:
            return ToolResult(
                content=f"Error editing file {file_path}: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
    
    def _count_occurrences(self, content: str, old: str) -> int:
        count = 0
        start = 0
        while True:
            start = content.find(old, start)
            if start == -1:
                break
            count += 1
            start += len(old)
        return count
    
    def _fuzzy_match(self, content: str, old: str) -> float:
        """计算简单相似度，帮助诊断匹配问题"""
        words = re.findall(r'\w+', old.lower())
        if not words:
            return 0.0
        content_lower = content.lower()
        matches = sum(1 for word in words if word in content_lower)
        return matches / len(words)
