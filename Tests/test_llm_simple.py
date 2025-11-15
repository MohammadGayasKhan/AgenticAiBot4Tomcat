"""Quick smoke script for the new LangChain remote chatbot."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, Sequence

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from RemoteAgent.chatbot import RemoteWorkflowChatBot
from langchain_core.messages import AIMessage


class DummyWorkflowTool:
    """In-memory stub so the demo can run without remote hosts."""

    def __init__(self) -> None:
        self.name = "remote_workflow"
        self.description = "Execute the full remote workflow (stubbed for tests)."

    def run(
        self,
        *,
        settings_path: str,
        servers_path: str,
        target_servers: Sequence[str],
    ) -> Dict[str, Any]:
        return {
            "status": "Success",
            "details": f"Simulated workflow via {settings_path} / {servers_path}",
            "results": [
                {
                    "server": target,
                    "pre_install_java": {"status": "Success"},
                    "install_tomcat": {"status": "Success"},
                }
                for target in target_servers
            ],
        }


class StubLLM:
    """Minimal LangChain-compatible LLM stub for automated tests."""

    def invoke(self, messages, **_: Any):
        last_content = messages[-1].content if messages else ""
        if "Server options" in last_content:
            return AIMessage(content="Please choose specific servers or type 'all'.")
        if "Workflow Plan Request" in last_content:
            plan = {
                "tasks": [
                    {
                        "tool": "remote_workflow",
                        "server": "all",
                        "params": {},
                    }
                ],
                "notes": "stub-plan",
            }
            return AIMessage(content=json.dumps(plan))
        if "Execution Summary Request" in last_content:
            return AIMessage(content="Workflow completed successfully for requested servers.")
        return AIMessage(content="Ack.")


def main() -> None:
    chatbot = RemoteWorkflowChatBot(
        workflow_tool=DummyWorkflowTool(),
        server_inventory=[
            {"name": "server.alpha", "host": "192.0.2.10"},
            {"name": "server.beta", "host": "192.0.2.11"},
        ],
        llm_client=StubLLM(),
    )

    print("Testing LangChain remote workflow chatbot...")
    print("=" * 70)

    first_response = chatbot.chat("Install Tomcat across all servers")
    print(f"\nBot: {first_response}\n")

    follow_up = chatbot.chat("all")
    print(f"\nBot: {follow_up}\n")
    print("=" * 70)


if __name__ == "__main__":
    main()
