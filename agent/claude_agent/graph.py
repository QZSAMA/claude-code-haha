"""
Claude Agent Graph Construction
使用LangGraph构建Claude Agent执行图
"""
from typing import Dict, Optional
from langgraph.graph import StateGraph, END
from claude_agent.state import AgentState
from claude_agent.nodes import (
    token_check_node,
    build_system_prompt_node,
    call_claude_node,
    execute_tools_node,
    should_continue_after_tools,
    compact_history_node,
    should_compact,
)


def build_claude_agent_graph(config: dict) -> StateGraph:
    """
    构建Claude Agent的LangGraph状态图
    
    流程图:
    1. token_check -> 检查是否需要压缩
    2. 如果需要压缩 -> compact -> build_system_prompt
    3. 如果不需要压缩 -> build_system_prompt
    4. build_system_prompt -> call_claude
    5. call_claude -> execute_tools
    6. execute_tools -> 判断是否继续:
       - 如果继续 -> token_check (loop back)
       - 如果结束 -> END
    
    Args:
        config: 配置字典，包含:
            - tool_registry: 工具注册表
            - api_client: Claude API客户端
            - agent_config: Agent配置
            - working_directory: 工作目录
    
    Returns:
        编译好的StateGraph
    """
    workflow = StateGraph(AgentState)
    
    workflow.add_node("token_check", lambda state: token_check_node(state, config))
    
    workflow.add_node("compact_history", lambda state: compact_history_node(state, config))
    
    workflow.add_node("build_system_prompt", lambda state: build_system_prompt_node(state, config))
    
    workflow.add_node("call_claude", lambda state: call_claude_node(state, config))
    
    workflow.add_node("execute_tools", lambda state: execute_tools_node(state, config))
    
    workflow.set_entry_point("token_check")
    
    workflow.add_conditional_edges(
        "token_check",
        should_compact,
        {
            "compact": "compact_history",
            "skip": "build_system_prompt",
        }
    )
    
    workflow.add_edge("compact_history", "build_system_prompt")
    
    workflow.add_edge("build_system_prompt", "call_claude")
    
    workflow.add_edge("call_claude", "execute_tools")
    
    workflow.add_conditional_edges(
        "execute_tools",
        should_continue_after_tools,
        {
            "continue": "token_check",
            "end": END,
        }
    )
    
    return workflow


def create_compiled_agent(config: dict):
    """创建编译好的agent"""
    graph = build_claude_agent_graph(config)
    return graph.compile()
