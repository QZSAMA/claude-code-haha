#!/usr/bin/env python3
"""
Claude Agent CLI - 基于LangGraph的Claude CLI重构
命令行交互入口
"""
import asyncio
import os
import sys
import argparse
from dotenv import load_dotenv
from claude_agent.agent import ClaudeAgent, create_agent
from claude_agent.state import AgentState


def load_env():
    """加载环境变量"""
    load_dotenv()
    return os.environ.get("ANTHROPIC_API_KEY")


async def interactive_session(
    agent: ClaudeAgent,
    initial_input: str = None,
):
    """
    交互式会话
    
    Args:
        agent: ClaudeAgent实例
        initial_input: 可选初始输入
    """
    print("🤖 Claude Agent - LangGraph Reconstruction")
    print("Type 'exit' or 'quit' to end the session")
    print("-" * 50)
    
    state: AgentState | None = None
    
    if initial_input:
        print(f"\n👤 User: {initial_input}")
        state = agent.get_initial_state(initial_input)
        state = await agent.run(state)
        response = agent.get_final_response(state)
        print(f"\n🤖 Claude: {response}")
        print("\n" + "-" * 50)
    else:
        state = None
    
    while True:
        try:
            user_input = input("\n👤 User: ")
        except (EOFError, KeyboardInterrupt):
            print("\n\nGoodbye!")
            break
        
        if user_input.lower() in ["exit", "quit", "q"]:
            print("\nGoodbye!")
            break
        
        if not user_input.strip():
            continue
        
        if state is None:
            state = agent.get_initial_state(user_input)
        else:
            state = agent.add_user_message(state, user_input)
        
        print("\n🤖 Claude: ", end="", flush=True)
        state = await agent.run(state)
        response = agent.get_final_response(state)
        print(response)
        
        usage = agent.get_token_usage(state)
        total = agent.get_estimated_total_tokens(state)
        print(f"\n[Token usage: {total} total, {usage.get('input', 0)} input, {usage.get('output', 0)} output]")
        print("-" * 50)


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="Claude Agent - LangGraph reconstruction of Claude CLI"
    )
    parser.add_argument(
        "--model",
        default="claude-3-5-sonnet-20241022",
        help="Model name to use",
    )
    parser.add_argument(
 "--max-tokens",
        type=int,
        default=200000,
        help="Maximum context tokens",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=4096,
        help="Maximum output tokens",
    )
    parser.add_argument(
        "--working-dir",
        default=os.getcwd(),
        help="Working directory",
    )
    parser.add_argument(
        "--api-key",
        help="Anthropic API key (defaults to ANTHROPIC_API_KEY env)",
    )
    parser.add_argument(
        "input",
        nargs="*",
        help="Input prompt (non-interactive)",
    )
    
    args = parser.parse_args()
    
    api_key = args.api_key or load_env()
    if not api_key:
        print("Error: ANTHROPIC_API_KEY not found in environment or --api-key")
        sys.exit(1)
    
    agent = create_agent(
        model=args.model,
        max_tokens=args.max_tokens,
        max_output_tokens=args.max_output_tokens,
        working_directory=args.working_dir,
        api_key=api_key,
    )
    
    if args.input:
        user_input = " ".join(args.input)
        asyncio.run(async_single_query(agent, user_input))
    else:
        asyncio.run(interactive_session(agent))


async def async_single_query(agent: ClaudeAgent, user_input: str):
    """单次查询"""
    state = agent.get_initial_state(user_input)
    state = await agent.run(state)
    response = agent.get_final_response(state)
    print(response)


if __name__ == "__main__":
    main()
