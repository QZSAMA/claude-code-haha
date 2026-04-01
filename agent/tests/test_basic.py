"""
Basic Tests
基础功能测试
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from claude_agent.state import AgentState, AgentConfig, ConversationTurn, ToolCall
from claude_agent.tools import ToolRegistry, FileReadTool, FileWriteTool, create_default_registry
from claude_agent.tools.base import ToolContext
from claude_agent.graph import build_claude_agent_graph


class TestState:
    """状态定义测试"""
    
    def test_agent_state_creation(self):
        """测试创建AgentState"""
        state = AgentState(
            messages=[{"role": "user", "content": "Hello"}],
            user_input="Hello",
        )
        assert state.user_input == "Hello"
        assert len(state.messages) == 1
        assert state.is_first_turn
        assert state.should_continue
        assert state.needs_compaction is False
    
    def test_agent_state_add_tool_call(self):
        """测试添加工具调用"""
        state = AgentState(
            messages=[{"role": "user", "content": "Hello"}],
            user_input="Hello",
        )
        turn = ConversationTurn(turn_id="test", user_input="Hello")
        state.current_turn = turn
        tc = ToolCall(id="test1", name="read", input={"file_path": "/test.txt"})
        state.add_tool_call(tc)
        assert len(state.tools_to_execute) == 1
        assert len(state.current_turn.tool_calls) == 1
    
    def test_agent_config_defaults(self):
        """测试默认配置"""
        config = AgentConfig()
        assert config.model == "claude-3-sonnet-20240229"
        assert config.max_tokens == 100000
        assert config.auto_compact_enabled is True
        assert config.streaming_enabled is True
    
    def test_needs_compaction(self):
        """测试压缩检测"""
        config = AgentConfig(max_tokens=1000, auto_compact_threshold=0.8)
        state = AgentState(estimated_tokens=801)
        assert state.needs_compaction_check(config.max_tokens, config.auto_compact_threshold)
        
        state = AgentState(estimated_tokens=800)
        assert not state.needs_compaction_check(config.max_tokens, config.auto_compact_threshold)


class TestToolRegistry:
    """工具注册表测试"""
    
    def test_create_default_registry(self):
        """测试创建默认注册表"""
        registry = create_default_registry(".")
        tools = registry.list_tools()
        assert len(tools) > 0
        assert "read" in registry.get_tool_names()
        assert "write" in registry.get_tool_names()
        assert "edit" in registry.get_tool_names()
        assert "glob" in registry.get_tool_names()
    
    def test_get_anthropic_tools_format(self):
        """测试获取Anthropic格式工具"""
        registry = create_default_registry(".")
        tools = registry.get_anthropic_tools()
        assert isinstance(tools, list)
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
    
    def test_get_tool(self):
        """测试获取工具"""
        registry = create_default_registry(".")
        read_tool = registry.get_tool("read")
        assert read_tool is not None
        assert read_tool.name == "read"
        assert read_tool.is_read_only({})
    
    def test_register_custom_tool(self):
        """测试注册自定义工具"""
        registry = ToolRegistry()
        from claude_agent.tools.base import BaseTool
        
        class CustomTool(BaseTool):
            name = "custom"
            description = "custom tool"
            input_schema = {"type": "object", "properties": {}}
            output_schema = {"type": "object", "properties": {}}
            
            async def check_permissions(self, input, context):
                from claude_agent.state import PermissionResult, PermissionBehavior
                return PermissionResult(behavior=PermissionBehavior.ALLOW)
            
            async def execute(self, input, context):
                from claude_agent.tools.base import ToolResult
                return ToolResult("ok", False)
        
        registry.register(CustomTool())
        assert "custom" in registry.get_tool_names()


class TestFileReadTool:
    """文件读取工具测试"""
    
    def test_input_schema(self):
        """测试输入schema"""
        tool = FileReadTool(".")
        assert "file_path" in tool.input_schema["properties"]
        assert "file_path" in tool.input_schema["required"]
    
    def test_is_read_only(self):
        """测试只读判断"""
        tool = FileReadTool(".")
        assert tool.is_read_only({"file_path": "test.txt"}) is True


class TestGraphBuilding:
    """图构建测试"""
    
    def test_build_graph(self):
        """测试构建图"""
        config = {
            "tool_registry": create_default_registry("."),
            "agent_config": AgentConfig(),
            "working_directory": ".",
        }
        graph = build_claude_agent_graph(config)
        assert graph is not None
        assert "token_check" in graph.nodes
        assert "compact_history" in graph.nodes
        assert "build_system_prompt" in graph.nodes
        assert "call_claude" in graph.nodes
        assert "execute_tools" in graph.nodes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
