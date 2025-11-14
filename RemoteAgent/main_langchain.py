"""CLI entry point for the LangChain-powered remote chatbot."""

from __future__ import annotations

from RemoteAgent.chatbot import build_dynamic_remote_tools
from RemoteAgent.inventory_tool import ServerInventoryTool
from RemoteAgent.langchain_chatbot import RemoteLangChainChatBot


def main() -> None:
    print("Initializing Remote SysCheck AI (LangChain remote chatbot)...\n")
    tools = build_dynamic_remote_tools()
    tools.append(ServerInventoryTool())
    chatbot = RemoteLangChainChatBot(tools)

    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                print("\nInput closed. Exiting remote chat. Goodbye!")
                break

            if not user_input:
                continue

            if user_input.lower() in {"exit", "quit", "bye"}:
                print("Exiting remote chat. Goodbye!")
                break

            print()
            response = chatbot.chat(user_input)
            print(f"\nBot: {response}\n")
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting remote chat. Goodbye!")


if __name__ == "__main__":
    main()
