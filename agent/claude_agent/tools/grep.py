"""
Grep Tool
使用ripgrep正则表达式搜索文件内容
"""
import os
import re
from typing import Dict, List, Tuple, Optional
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class GrepTool(BaseTool):
    """Grep内容搜索工具"""
    
    name = "grep"
    description = (
        "A powerful search tool built on ripgrep. "
        "ALWAYS use Grep for search tasks. NEVER invoke grep or rg as a Bash command. "
        "Supports full regex syntax. Filter files with glob parameter. "
        "Use the Agent tool for open-ended searches requiring multiple rounds. "
        "Pattern syntax: uses ripgrep - literal braces need escaping."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "The regular expression pattern to search for in file contents",
            },
            "path": {
                "type": "string",
                "description": "The directory or file to search in, defaults to current working directory",
            },
            "glob": {
                "type": "string",
                "description": "Glob pattern to filter files (e.g., *.py, **/*.tsx)",
            },
            "output_mode": {
                "type": "string",
                "description": "Output mode: content (shows matching lines), files_with_matches (only file paths), count",
                "enum": ["content", "files_with_matches", "count"],
                "default": "content",
            },
            "output_n": {
                "type": "boolean",
                "description": "Show line numbers in content output, default false",
                "default": False,
            },
            "case_insensitive": {
                "type": "boolean",
                "description": "Case insensitive search, default false",
                "default": False,
            },
            "type": {
                "type": "string",
                "description": "Filter by file type (e.g., py, ts, js)",
            },
        },
        "required": ["pattern"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "matches": {"type": "array", "items": {"type": "object"}},
            "total_matches": {"type": "integer"},
            "files_searched": {"type": "integer"},
        },
    }
    
    max_result_size_chars = 100_000
    is_concurrency_safe = True
    max_matches = 500
    max_files = 1000
    
    def is_read_only(self, input_params: Dict) -> bool:
        return True
    
    async def check_permissions(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> PermissionResult:
        return PermissionResult(behavior=PermissionBehavior.ALLOW)
    
    def _match_files(self, search_path: str, glob_pattern: Optional[str]) -> List[str]:
        """匹配文件"""
        import glob
        if glob_pattern:
            if search_path and os.path.isdir(search_path):
                pattern = os.path.join(search_path, glob_pattern)
            else:
                pattern = glob_pattern
            files = glob.glob(pattern, recursive=True)
        else:
            files = []
            for root, _, filenames in os.walk(search_path):
                for filename in filenames:
                    files.append(os.path.join(root, filename))
        
        files = [f for f in files if os.path.isfile(f)]
        if len(files) > self.max_files:
            files = files[:self.max_files]
        return files
    
    def _search_file(
        self,
        file_path: str,
        pattern: str,
        flags: int,
    ) -> List[Tuple[int, str]]:
        """在单个文件中搜索"""
        matches = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, 1):
                    if re.search(pattern, line, flags=flags):
                        matches.append((line_num, line.rstrip()))
        except Exception:
            pass
        return matches
    
    async def execute(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> ToolResult:
        pattern = input_params["pattern"]
        search_path = input_params.get("path", context.working_directory)
        glob_pattern = input_params.get("glob")
        output_mode = input_params.get("output_mode", "content")
        show_line_numbers = input_params.get("output_n", False)
        case_insensitive = input_params.get("case_insensitive", False)
        file_type = input_params.get("type")
        
        try:
            if not os.path.exists(search_path):
                return ToolResult(
                    content=f"Error: Path does not exist: {search_path}",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            flags = re.MULTILINE
            if case_insensitive:
                flags |= re.IGNORECASE
            
            if file_type and not glob_pattern:
                glob_pattern = f"**/*.{file_type}"
            
            files = self._match_files(search_path, glob_pattern)
            if not files:
                return ToolResult(
                    content=f"No files found matching glob: {glob_pattern}",
                    is_error=False,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            all_matches = []
            total_matches = 0
            
            for file_path in files:
                matches = self._search_file(file_path, pattern, flags)
                if matches:
                    for line_num, line_text in matches:
                        all_matches.append({
                            "file": file_path,
                            "line_num": line_num,
                            "line": line_text,
                        })
                        total_matches += 1
            
            if output_mode == "count":
                content = f"Found {total_matches} matches in {len(files)} files"
                return ToolResult(
                    content=content,
                    is_error=False,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            elif output_mode == "files_with_matches":
                unique_files = sorted(set(m["file"] for m in all_matches))
                content_lines = [f"Found {len(unique_files)} files with {total_matches} matches:"]
                for f in unique_files:
                    content_lines.append(f"- {f}")
                content = "\n".join(content_lines)
                return ToolResult(
                    content=content,
                    is_error=False,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            else:
                if total_matches == 0:
                    return ToolResult(
                        content=f"No matches found for pattern: {pattern}",
                        is_error=False,
                        execution_time_ms=context.get_elapsed_ms(),
                    )
                
                if total_matches > self.max_matches:
                    all_matches = all_matches[:self.max_matches]
                    truncated = True
                else:
                    truncated = False
                
                output_lines = []
                for match in all_matches:
                    if show_line_numbers:
                        output_lines.append(f"{match['file']}:{match['line_num']}: {match['line']}")
                    else:
                        output_lines.append(f"{match['file']}: {match['line']}")
                
                if truncated:
                    output_lines.append(f"\n(Results truncated after {self.max_matches} matches)")
                
                content = "\n".join(output_lines)
                return ToolResult(
                    content=content,
                    is_error=False,
                    execution_time_ms=context.get_elapsed_ms(),
                )
        
        except re.error as e:
            return ToolResult(
                content=f"Invalid regex pattern: {pattern}\nError: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
        except Exception as e:
            return ToolResult(
                content=f"Error searching: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
