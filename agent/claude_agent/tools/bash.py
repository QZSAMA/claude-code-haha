"""
Bash Tool
在Bash shell中执行命令
"""
import asyncio
import os
import shlex
import sys
from typing import Dict, Optional
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class BashTool(BaseTool):
    """Bash命令执行工具"""
    
    name = "bash"
    description = (
        "Executes a given bash command and returns its output. "
        "The working directory persists between commands, but shell state does not. "
        "IMPORTANT: Avoid using this tool to write to files, delete files, or modify the filesystem "
        "unless explicitly instructed or after you have verified that a dedicated tool cannot accomplish your task. "
        "Instead, use the appropriate dedicated tool for file operations."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The bash command to execute",
            },
            "timeout": {
                "type": "integer",
                "description": "Optional timeout in seconds, default 120",
                "minimum": 1,
                "default": 120,
            },
        },
        "required": ["command"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "output": {
                "type": "string",
                "description": "Command output (stdout + stderr)",
            },
            "exit_code": {
                "type": "integer",
                "description": "Exit code from the command",
            },
            "execution_time_ms": {
                "type": "integer",
                "description": "Execution time in milliseconds",
            },
        },
    }
    
    max_result_size_chars = 200_000
    is_concurrency_safe = False
    default_timeout = 120
    
    def is_read_only(self, input_params: Dict) -> bool:
        command = input_params["command"]
        return self._is_read_only_command(command)
    
    def _is_read_only_command(self, command: str) -> bool:
        """检查命令是否只读"""
        read_only_keywords = [
            "cat", "grep", "find", "ls", "pwd", "cd", "echo", "head", "tail",
            "wc", "sort", "uniq", "diff", "test", "which", "whereis", "history",
            "git status", "git diff", "git log", "git show", "git branch",
            "ps", "top", "free", "df", "du", "uname", "env", "export",
        ]
        command_lower = command.lower()
        for kw in read_only_keywords:
            if kw in command_lower:
                return True
        return False
    
    async def check_permissions(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> PermissionResult:
        command = input_params["command"]
        if self._is_read_only_command(command):
            return PermissionResult(behavior=PermissionBehavior.ALLOW)
        
        return PermissionResult(
            behavior=PermissionBehavior.ASK,
            message=f"Command may modify filesystem: {command[:100]}...",
        )
    
    async def execute(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> ToolResult:
        command = input_params["command"]
        timeout = input_params.get("timeout", self.default_timeout)
        
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=context.working_directory,
            )
            
            try:
                stdout, _ = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return ToolResult(
                    content=f"Command timed out after {timeout} seconds: {command}",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            
            exit_code = proc.returncode
            output = stdout.decode("utf-8", errors="replace")
            
            if len(output) > self.max_result_size_chars:
                output = output[:self.max_result_size_chars] + "\n\n... (output truncated due to size limit)"
            
            if exit_code == 0:
                return ToolResult(
                    content=output,
                    is_error=False,
                    execution_time_ms=context.get_elapsed_ms(),
                )
            else:
                return ToolResult(
                    content=f"Command exited with code {exit_code}\n\n{output}",
                    is_error=True,
                    execution_time_ms=context.get_elapsed_ms(),
                )
        
        except Exception as e:
            return ToolResult(
                content=f"Error executing command: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
