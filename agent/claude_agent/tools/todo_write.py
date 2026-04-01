"""
TodoWrite Tool
管理待办事项列表工具
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class TodoItem(BaseModel):
    """待办事项"""
    id: str
    content: str
    status: str  # pending, in_progress, completed
    priority: str  # high, medium, low
    
    def to_dict(self) -> Dict:
        return self.model_dump()


class TodoWriteTool(BaseTool):
    """管理待办事项列表工具"""
    
    name = "todo_write"
    description = (
        "Use this tool to create and manage a structured task list for your current coding session. "
        "This helps you track progress, organize complex tasks, and demonstrates thoroughness to the user."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "todos": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {
                            "type": "string",
                            "description": "Unique task identifier",
                        },
                        "content": {
                            "type": "string",
                            "description": "Task description in imperative form",
                        },
                        "status": {
                            "type": "string",
                            "description": "Task status: pending, in_progress, completed",
                            "enum": ["pending", "in_progress", "completed"],
                        },
                        "priority": {
                            "type": "string",
                            "description": "Priority: high, medium, low",
                            "enum": ["high", "medium", "low"],
                        },
                    },
                    "required": ["id", "content", "status", "priority"],
                },
            },
            "summary": {
                "type": "string",
                "description": "User-friendly summary of what work was actually finished "
                           "when one or more tasks transition from non-completed to completed.",
            },
        },
        "required": ["todos"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "message": {"type": "string"},
            "task_count": {"type": "integer"},
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
        return PermissionResult(behavior=PermissionBehavior.ALLOW)
    
    async def execute(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> ToolResult:
        todos_data = input_params["todos"]
        summary = input_params.get("summary", "")
        
        try:
            validated_todos = []
            for todo in todos_data:
                validated_todos.append(TodoItem(**todo))
            
            todo_file = os.path.join(context.working_directory, ".todo.json")
            
            output_data = {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "summary": summary,
                "todos": [t.to_dict() for t in validated_todos],
                "stats": {
                    "total": len(validated_todos),
                    "pending": sum(1 for t in validated_todos if t.status == "pending"),
                    "in_progress": sum(1 for t in validated_todos if t.status == "in_progress"),
                    "completed": sum(1 for t in validated_todos if t.status == "completed"),
                }
            }
            
            with open(todo_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            
            stats = output_data["stats"]
            message = (
                f"Todo list updated successfully:\n"
                f"  Total: {stats['total']}\n"
                f"  Pending: {stats['pending']}\n"
                f"  In Progress: {stats['in_progress']}\n"
                f"  Completed: {stats['completed']}"
            )
            if summary:
                message += f"\n\nSummary: {summary}"
            
            return ToolResult(
                content=message,
                is_error=False,
                execution_time_ms=context.get_elapsed_ms(),
            )
        
        except Exception as e:
            return ToolResult(
                content=f"Error updating todo list: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
