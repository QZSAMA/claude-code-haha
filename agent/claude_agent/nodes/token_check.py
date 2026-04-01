"""
Token Check Node
检查token占用，决定是否需要压缩
"""
from typing import Dict
from claude_agent.state import AgentState, AgentConfig


def token_check_node(state: AgentState, config: AgentConfig) -> Dict:
    """
    检查当前token使用量，判断是否需要压缩
    
    Args:
        state: 当前agent状态
        config: agent配置
    
    Returns:
        更新后的状态字典
    """
    state.update_timestamp()
    
    if not config.auto_compact_enabled:
        return {
            "needs_compaction": False,
            "estimated_tokens": state.estimated_tokens,
        }
    
    needs_compaction = state.needs_compaction_check(
        config.max_tokens,
        config.auto_compact_threshold,
    )
    
    return {
        "needs_compaction": needs_compaction,
        "estimated_tokens": state.estimated_tokens,
    }
