"""
WebSearch Tool
网络搜索工具，获取实时信息
"""
import json
import os
from typing import Dict, List, Optional
import httpx
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class WebSearchTool(BaseTool):
    """网络搜索工具"""
    
    name = "web_search"
    description = (
        "Allows Claude to search the web and use the results to inform responses. "
        "Provides up-to-date information for current events and recent data. "
        "[CRITICAL] After answering, MUST include \"Sources:\" section listing all URLs."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to use",
                "minLength": 2,
            },
            "allowed_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of domains to limit search to",
            },
            "blocked_domains": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional list of domains to block from results",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "results": {"type": "array"},
            "duration_seconds": {"type": "number"},
        },
    }
    
    max_result_size_chars = 100_000
    is_concurrency_safe = True
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__()
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    
    def is_read_only(self, input_params: Dict) -> bool:
        return True
    
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
        query = input_params["query"]
        allowed_domains = input_params.get("allowed_domains")
        blocked_domains = input_params.get("blocked_domains")
        
        if not self.api_key:
            return ToolResult(
                content="Error: ANTHROPIC_API_KEY not set for web search",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
        
        try:
            from datetime import datetime
            start_time = datetime.now()
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers = {
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "query": query,
                }
                if allowed_domains:
                    payload["allowed_domains"] = allowed_domains
                if blocked_domains:
                    payload["blocked_domains"] = blocked_domains
                
                response = await client.post(
                    "https://api.anthropic.com/v1/search",
                    headers=headers,
                    json=payload,
                )
                
                if response.status_code != 200:
                    return ToolResult(
                        content=f"Web search failed: HTTP {response.status_code}\n{response.text}",
                        is_error=True,
                        execution_time_ms=context.get_elapsed_ms(),
                    )
                
                data = response.json()
                duration = (datetime.now() - start_time).total_seconds()
                
                output_lines = [f"Search results for: {query}"]
                output_lines.append("")
                
                results = data.get("results", [])
                for i, result in enumerate(results, 1):
                    title = result.get("title", "No title")
                    url = result.get("url", "No URL")
                    snippet = result.get("snippet", "No snippet")
                    output_lines.append(f"{i}. **{title}**")
                    output_lines.append(f"URL: {url}")
                    output_lines.append(f"Snippet: {snippet}")
                    output_lines.append("")
                
                content = "\n".join(output_lines)
                return ToolResult(
                    content=content,
                    is_error=False,
                    execution_time_ms=context.get_elapsed_ms(),
                )
        
        except Exception as e:
            return ToolResult(
                content=f"Error executing web search: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
