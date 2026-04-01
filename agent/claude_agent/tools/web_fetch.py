"""
WebFetch Tool
获取网页内容并转换为Markdown
"""
import os
import re
from typing import Dict, Optional
import httpx
from claude_agent.state import PermissionResult, PermissionBehavior
from claude_agent.tools.base import BaseTool, ToolContext, ToolResult


class WebFetchTool(BaseTool):
    """获取网页内容工具"""
    
    name = "web_fetch"
    description = (
        "Fetches content from a specified URL, converts HTML to markdown. "
        "Handles redirects and content extraction automatically."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to fetch content from",
            },
        },
        "required": ["url"],
        "additionalProperties": False,
    }
    output_schema = {
        "type": "object",
        "properties": {
            "content": {"type": "string"},
            "url": {"type": "string"},
            "title": {"type": "string"},
            "content_length": {"type": "integer"},
        },
    }
    
    max_result_size_chars = 200_000
    is_concurrency_safe = True
    
    def is_read_only(self, input_params: Dict) -> bool:
        return True
    
    async def check_permissions(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> PermissionResult:
        return PermissionResult(behavior=PermissionBehavior.ALLOW)
    
    def _clean_html(self, html: str) -> str:
        """简单HTML到Markdown转换"""
        text = html
        
        text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<noscript.*?</noscript>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<header.*?</header>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<footer.*?</footer>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<nav.*?</nav>', '', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<aside.*?</aside>', '', text, flags=re.DOTALL | re.I)
        
        text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<h4[^>]*>(.*?)</h4>', r'\n#### \1\n', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<ul[^>]*>(.*?)</ul>', r'\n\1\n', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text, flags=re.DOTALL | re.I)
        text = re.sub(r'<br\s*/?>\n?', r'\n', text, flags=re.I)
        
        text = re.sub(r'<[^>]+>', '', text)
        
        text = re.sub(r'\n\s*\n', r'\n\n', text)
        
        return text.strip()
    
    def _extract_title(self, html: str) -> Optional[str]:
        """提取页面标题"""
        match = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.DOTALL)
        if match:
            return self._clean_html(match.group(1)).strip()
        return None
    
    async def execute(
        self,
        input_params: Dict,
        context: ToolContext,
    ) -> ToolResult:
        url = input_params["url"]
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
                
                title = self._extract_title(html)
                content = self._clean_html(html)
                
                if len(content) > self.max_result_size_chars:
                    content = content[:self.max_result_size_chars] + "\n\n... (content truncated due to size limit)"
                
                output_lines = []
                if title:
                    output_lines.append(f"# {title}")
                    output_lines.append("")
                output_lines.append(f"URL: {url}")
                output_lines.append("")
                output_lines.append(content)
                
                final_content = "\n".join(output_lines)
                return ToolResult(
                    content=final_content,
                    is_error=False,
                    execution_time_ms=context.get_elapsed_ms(),
                )
        
        except Exception as e:
            return ToolResult(
                content=f"Error fetching URL {url}: {str(e)}",
                is_error=True,
                execution_time_ms=context.get_elapsed_ms(),
            )
