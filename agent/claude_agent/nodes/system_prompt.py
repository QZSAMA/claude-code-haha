"""
System Prompt Node
构建完整的系统提示词
"""
import datetime
from typing import Dict
from claude_agent.state import AgentState, AgentConfig
from claude_agent.tools import ToolRegistry


class SystemPromptBuilder:
    """系统提示构建器"""
    
    def __init__(
        self,
        tool_registry: ToolRegistry,
        working_directory: str,
        additional_working_directories: list[str] | None = None,
    ):
        self.tool_registry = tool_registry
        self.working_directory = working_directory
        self.additional_working_directories = additional_working_directories or []
    
    def get_knowledge_cutoff(self, model: str) -> str:
        """根据模型获取知识截止日期"""
        if "claude-3-5" in model.lower() or "claude-3.5" in model.lower():
            return "April 2024"
        elif "claude-3" in model.lower():
            return "February 2024"
        else:
            return "July 2024"
    
    def build_system_prompt(self, model: str) -> str:
        """构建完整系统提示"""
        cutoff = self.get_knowledge_cutoff(model)
        
        env_info = self._build_env_info()
        
        prompt_parts = [
            self._get_intro_section(),
            self._get_system_section(),
            self._get_guidelines_section(),
            self._get_actions_section(),
            self._get_tools_section(),
            env_info,
            self._get_output_efficiency_section(),
            self._get_tone_section(),
        ]
        
        return "\n\n".join(filter(None, prompt_parts))
    
    def _get_intro_section(self) -> str:
        return """You are Claude, an AI assistant built by Anthropic to be helpful, harmless, and honest.
You are running in Claude Code CLI, a terminal-based interactive development environment.
You have full access to the local filesystem and can execute commands.
"""
    
    def _get_system_section(self) -> str:
        return """You are working in a local codebase on the user's machine.
Your goal is to help the user with software development tasks including:
- Reading and understanding existing code
- Writing new code and features
- Debugging and fixing issues
- Refactoring and improving code quality
- Searching for information in the codebase
"""
    
    def _get_guidelines_section(self) -> str:
        return """## Guidelines

1. **Be accurate**: Double-check your references to the codebase. Don't guess the contents of files you haven't read.
2. **Be efficient**: Use tools to find information instead of asking the user.
3. **Be concise**: Prefer shorter answers when appropriate, but don't sacrifice clarity.
4. **Think step by step**: Work through problems systematically.
5. **Use tools**: Always use the appropriate tool instead of guessing or doing manual work.
"""
    
    def _get_actions_section(self) -> str:
        return """## Actions

When performing actions that modify the filesystem:
- Always think carefully about what you're doing
- Double-check file paths before writing
- Prefer editing existing files over creating new ones
- Follow the existing code style of the project
"""
    
    def _get_tools_section(self) -> str:
        return self.tool_registry.get_system_prompt_tools_section()
    
    def _build_env_info(self) -> str:
        import platform
        lines = ["## Environment Information"]
        lines.append(f"- Current working directory: {self.working_directory}")
        if self.additional_working_directories:
            lines.append(f"- Additional working directories: {', '.join(self.additional_working_directories)}")
        lines.append(f"- OS: {platform.system()} {platform.release()}")
        lines.append(f"- Date: {datetime.date.today().isoformat()}")
        return "\n".join(lines)
    
    def _get_output_efficiency_section(self) -> str:
        return """## Output Efficiency

- Use markdown formatting for readability
- When showing code, include line numbers if appropriate
- Truncate large outputs that exceed token limits
- Focus on the most relevant information
"""
    
    def _get_tone_section(self) -> str:
        return """## Tone and Style

- Professional but conversational
- Focus on solving the user's problem
- Explain your reasoning when it's helpful
- Keep responses clear and well-organized
"""


def build_system_prompt_node(state: AgentState, config: dict) -> Dict:
    """
    LangGraph节点：构建系统提示
    
    Args:
        state: 当前agent状态
        config: 配置，包含tool_registry
    
    Returns:
        更新后的状态字典
    """
    tool_registry = config.get("tool_registry")
    working_dir = state.working_directory or config.get("working_directory", ".")
    additional_dirs = state.additional_working_directories or []
    
    builder = SystemPromptBuilder(tool_registry, working_dir, additional_dirs)
    system_prompt = builder.build_system_prompt(state.model)
    
    return {
        "system_prompt": system_prompt,
        "available_tools": tool_registry.get_tool_names(),
    }
