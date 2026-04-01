"""
Call Claude Node
调用Anthropic Claude API获取模型响应
"""
import os
import asyncio
from typing import Dict, List, Optional
import anthropic
from claude_agent.state import AgentState, AgentConfig, ToolCall, ContentBlockType


class ClaudeAPIClient:
    """Anthropic Claude API客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")
        
        self.client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            base_url=base_url,
        )
    
    async def query(
        self,
        model: str,
        system_prompt: str,
        messages: List[Dict],
        max_tokens: int,
        temperature: float = 0.0,
        top_p: float = 1.0,
        tools: Optional[List[Dict]] = None,
    ) -> Dict:
        """调用Claude API获取响应"""
        params = {
            "model": model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
        }
        
        if tools:
            params["tools"] = tools
        
        response = await self.client.messages.create(**params)
        
        return self._parse_response(response)
    
    async def query_streaming(
        self,
        model: str,
        system_prompt: str,
        messages: List[Dict],
        max_tokens: int,
        temperature: float = 0.0,
        top_p: float = 1.0,
        tools: Optional[List[Dict]] = None,
        on_delta=None,
    ) -> Dict:
        """流式调用Claude API"""
        params = {
            "model": model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
        }
        
        if tools:
            params["tools"] = tools
        
        tool_calls: List[ToolCall] = []
        current_text = ""
        current_tool_id: Optional[str] = None
        current_tool_name: Optional[str] = None
        current_tool_input = ""
        stop_reason = None
        usage = None
        
        async with self.client.messages.stream(**params) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use":
                        current_tool_id = event.content_block.id
                        current_tool_name = event.content_block.name
                        current_tool_input = ""
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        current_text += delta.text
                        if on_delta:
                            await on_delta(delta.text)
                    elif delta.type == "input_json_delta":
                        current_tool_input += delta.partial_json
                elif event.type == "content_block_stop":
                    if current_tool_id and current_tool_name:
                        import json
                        try:
                            input_dict = json.loads(current_tool_input)
                        except json.JSONDecodeError:
                            input_dict = {}
                        tool_calls.append(ToolCall(
                            id=current_tool_id,
                            name=current_tool_name,
                            input=input_dict,
                        ))
                        current_tool_id = None
                        current_tool_name = None
                        current_tool_input = ""
                elif event.type == "message_stop":
                    pass
                elif event.type == "message_delta":
                    if hasattr(event, "delta") and hasattr(event.delta, "stop_reason"):
                        stop_reason = event.delta.stop_reason
                    if hasattr(event, "usage"):
                        usage = event.usage
        
        return {
            "text": current_text,
            "tool_calls": tool_calls,
            "stop_reason": stop_reason,
            "usage": usage,
        }
    
    def _parse_response(self, response) -> Dict:
        """解析非流式响应"""
        tool_calls: List[ToolCall] = []
        current_text = ""
        
        for block in response.content:
            if block.type == "text":
                current_text += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    input=block.input,
                ))
        
        return {
            "text": current_text,
            "tool_calls": tool_calls,
            "stop_reason": response.stop_reason,
            "usage": response.usage,
        }


def extract_tool_calls(response: Dict) -> List[ToolCall]:
    """从响应提取工具调用"""
    return response.get("tool_calls", [])


async def call_claude_node(state: AgentState, config: dict) -> Dict:
    """
    LangGraph节点：调用Claude API
    
    Args:
        state: 当前agent状态
        config: 配置，包含api_client, agent_config, tool_registry
    
    Returns:
        更新后的状态字典
    """
    api_client = config.get("api_client")
    agent_config = config.get("agent_config")
    tool_registry = config.get("tool_registry")
    
    messages = state.to_anthropic_messages()
    system_prompt = state.system_prompt
    model = state.model or agent_config.model
    max_tokens = agent_config.max_output_tokens
    
    tools = tool_registry.get_anthropic_tools()
    
    response = await api_client.query_streaming(
        model=model,
        system_prompt=system_prompt,
        messages=messages,
        max_tokens=max_tokens,
        temperature=agent_config.temperature,
        top_p=agent_config.top_p,
        tools=tools,
    )
    
    tool_calls = extract_tool_calls(response)
    
    text_response = response.get("text", "")
    
    assistant_message = {
        "role": "assistant",
        "content": text_response,
    }
    
    if tool_calls:
        content_blocks = []
        if text_response:
            content_blocks.append({
                "type": "text",
                "text": text_response,
            })
        for tc in tool_calls:
            content_blocks.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.input,
            })
        assistant_message["content"] = content_blocks
    
    usage = response.get("usage")
    token_usage = dict(state.token_usage)
    if usage:
        token_usage["input"] = usage.input_tokens
        token_usage["output"] = usage.output_tokens
    
    estimated_tokens = state.estimated_tokens + sum(token_usage.values())
    
    return {
        "messages": [assistant_message],
        "tools_to_execute": tool_calls,
        "stop_reason": response.get("stop_reason"),
        "token_usage": token_usage,
        "estimated_tokens": estimated_tokens,
        "executing_tools": len(tool_calls) > 0,
    }
