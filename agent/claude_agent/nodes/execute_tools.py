"""
Execute Tools Node
执行工具调用并收集结果
"""
import asyncio
from typing import Dict, List
from claude_agent.state import AgentState, ToolResult, ToolCall
from claude_agent.tools import ToolRegistry, BaseTool, ToolContext, ToolResult as ToolResultObj
from claude_agent.state import PermissionResult, PermissionBehavior


async def execute_single_tool(
    tool: BaseTool,
    tool_call: ToolCall,
    context: ToolContext,
) -> Dict:
    """执行单个工具调用"""
    valid, error = tool.validate_input(tool_call.input)
    if not valid:
        return {
            "tool_use_id": tool_call.id,
            "content": f"Input validation failed: {error}",
            "is_error": True,
        }
    
    permission = await tool.check_permissions(tool_call.input, context)
    if permission.behavior == PermissionBehavior.DENY:
        return {
            "tool_use_id": tool_call.id,
            "content": f"Permission denied: {permission.message}",
            "is_error": True,
        }
    elif permission.behavior == PermissionBehavior.ASK:
        return {
            "tool_use_id": tool_call.id,
            "content": f"User approval required: {permission.message}",
            "is_error": True,
        }
    
    try:
        result = await tool.execute(tool_call.input, context)
        return {
            "tool_use_id": tool_call.id,
            "content": result.content,
            "is_error": result.is_error,
            "execution_time_ms": result.execution_time_ms,
        }
    except Exception as e:
        return {
            "tool_use_id": tool_call.id,
            "content": f"Tool execution exception: {str(e)}",
            "is_error": True,
        }


async def execute_tools_node(state: AgentState, config: dict) -> Dict:
    """
    LangGraph节点：执行所有待执行的工具调用
    
    Args:
        state: 当前agent状态
        config: 配置，包含tool_registry, working_directory
    
    Returns:
        更新后的状态字典
    """
    tool_registry: ToolRegistry = config.get("tool_registry")
    working_directory = state.working_directory or config.get("working_directory", ".")
    
    tool_calls = state.tools_to_execute
    if not tool_calls:
        return {
            "executing_tools": False,
            "tools_to_execute": [],
        }
    
    context = ToolContext(working_directory=working_directory)
    
    tool_results: List[Dict] = []
    messages_to_add: List[Dict] = []
    
    for tool_call in tool_calls:
        tool = tool_registry.get_tool(tool_call.name)
        if tool is None:
            result_dict = {
                "tool_use_id": tool_call.id,
                "content": f"Tool not found: {tool_call.name}",
                "is_error": True,
            }
            tool_results.append(result_dict)
            continue
        
        result_dict = await execute_single_tool(tool, tool_call, context)
        tool_results.append(result_dict)
        
        tool_result_msg = {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": result_dict["content"],
                    "is_error": result_dict.get("is_error", False),
                }
            ]
        }
        messages_to_add.append(tool_result_msg)
        
        if state.current_turn:
            state.add_tool_result(ToolResult(**result_dict))
    
    state.update_timestamp()
    
    return {
        "messages": messages_to_add,
        "tools_to_execute": [],
        "executing_tools": False,
        "should_continue": len(tool_results) > 0,
    }


def should_continue_after_tools(state: AgentState) -> str:
    """
    条件边：决定工具执行后是否继续查询
    
    Returns:
        "continue" -> 需要继续调用Claude
        "end" -> 结束当前回合
    """
    if state.executing_tools:
        return "continue"
    
    if state.should_continue and state.stop_reason != "end_turn":
        return "continue"
    
    return "end"
