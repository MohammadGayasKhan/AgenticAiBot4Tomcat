"""CLI entry point for the consolidated LangChain remote workflow chatbot."""

from __future__ import annotations

import argparse

from RemoteAgent.chatbot import (
    DEFAULT_SERVERS_PATH,
    DEFAULT_SETTINGS_PATH,
    RemoteWorkflowChatBot,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Remote LangChain chatbot")
    parser.add_argument(
        "--settings",
        default=DEFAULT_SETTINGS_PATH,
        help="Path to remote workflow settings YAML (default: Remote/config/settings.yaml)",
    )
    parser.add_argument(
        "--servers",
        default=DEFAULT_SERVERS_PATH,
        help="Path to remote servers inventory ini (default: Remote/config/servers.ini)",
    )
    parser.add_argument(
        "--model",
        default="llama3.1",
        help="Ollama model name to use (default: llama3.1)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="LLM temperature (default: 0.2)",
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    print("Initializing Remote Workflow ChatBot (LangChain)...\n")
    chatbot = RemoteWorkflowChatBot(
        model_name=args.model,
        temperature=args.temperature,
        settings_path=args.settings,
        servers_path=args.servers,
    )

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
