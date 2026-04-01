"""
Compaction Node
上下文压缩节点，当token超限压缩历史
"""
from typing import Dict, List
from claude_agent.state import AgentState, AgentConfig


async def compact_history_node(state: AgentState, config: dict) -> Dict:
    """
    压缩对话历史，减少token占用
    
    Args:
        state: 当前agent状态
        config: 配置，包含api_client, agent_config
    
    Returns:
        更新后的状态字典
    """
    api_client = config.get("api_client")
    agent_config = config.get("agent_config")
    
    if not state.needs_compaction:
        return {
            "is_compacting": False,
            "needs_compaction": False,
        }
    
    messages = state.messages
    
    if len(messages) <= 2:
        return {
            "is_compacting": False,
            "needs_compaction": False,
        }
    
    compact_prompt = _build_compact_prompt(messages)
    
    response = await api_client.query(
        model=state.model or agent_config.model,
        system_prompt=_get_compact_system_prompt(),
        messages=[{"role": "user", "content": compact_prompt}],
        max_tokens=agent_config.max_output_tokens_for_summary,
    )
    
    summary = response.get("text", "Compaction failed")
    
    compact_boundary = {
        "role": "user",
        "content": "[COMPACT BOUNDARY - Earlier conversation has been summarized below]",
    }
    
    summary_message = {
        "role": "user",
        "content": f"## Conversation Summary\n\n{summary}",
    }
    
    keep_last_n = 4
    if len(messages) > keep_last_n:
        new_messages = [compact_boundary, summary_message] + messages[-keep_last_n:]
    else:
        new_messages = [compact_boundary, summary_message]
    
    total_tokens = sum(state.token_usage.values())
    estimated_tokens = _estimate_tokens(summary) + sum(
        _estimate_tokens(msg.get("content", "")) for msg in messages[-keep_last_n:]
    )
    
    return {
        "messages": new_messages,
        "messages_history": [state.messages],
        "compacted_history": summary,
        "is_compacting": False,
        "needs_compaction": False,
        "estimated_tokens": estimated_tokens,
    }


def _estimate_tokens(text: str) -> int:
    """粗略估计token数量，~4 chars per token"""
    if isinstance(text, str):
        return len(text) // 4
    elif isinstance(text, list):
        total = 0
        for block in text:
            if block.get("type") == "text":
                total += len(block.get("text", "")) // 4
            elif block.get("type") == "tool_result":
                content = block.get("content", "")
                if isinstance(content, str):
                    total += len(content) // 4
        return total
    return 0


def _build_compact_prompt(messages: List[Dict]) -> str:
    """构建压缩提示"""
    lines = [
        "Please create a detailed summary of the conversation above.",
        "Include the following sections in your summary:",
        "1. **Main Request**: What is the user asking for?",
        "2. **Key Concepts**: What are the important technical concepts discussed?",
        "3. **Files and Code**: What files and functions have been worked on?",
        "4. **Errors and Fixes**: What errors were encountered and how were they fixed?",
        "5. **Problem Solving**: What decisions were made and what problems solved?",
        "6. **Pending Tasks**: What tasks are still pending?",
        "7. **Current State**: What is currently being worked on?",
        "",
        "Format your response with:",
        "<analysis>Your analysis of what needs to be preserved goes here</analysis>",
        "<summary>The actual summarized conversation goes here</summary>",
        "",
        "Conversation to summarize:",
        "---",
    ]
    
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if isinstance(content, list):
            content_str = " ".join(
                block.get("text", block.get("content", ""))
                for block in content
            )
        else:
            content_str = str(content)
        lines.append(f"\n**{role.upper()}**: {content_str[:500]}...")
    
    lines.append("\n---")
    
    return "\n".join(lines)


def _get_compact_system_prompt() -> str:
    """获取压缩系统提示"""
    return """You are a conversation compression assistant for Claude Code.
Your task is to create a detailed summary of an extended conversation that fits within the token budget.
Preserve all important technical details, code references, file paths, error messages, and decisions.
Do not omit critical information that affects the current context.
Follow the required section format exactly.
"""


def should_compact(state: AgentState) -> str:
    """
    条件边：决定是否需要压缩
    
    Returns:
        "compact" -> 需要压缩
        "skip" -> 跳过压缩
    """
    if state.needs_compaction:
        return "compact"
    return "skip"
