"""LangChain-powered chatbot tailored for remote automation."""

from __future__ import annotations

from typing import Any, Iterable

from langchain.agents import create_react_agent
from langchain_core.prompts import PromptTemplate

from chatbot_langchain import LangChainChatBot


class RemoteLangChainChatBot(LangChainChatBot):
    """Specialized LangChain chatbot with remote administration persona."""

    def __init__(self, tools: Iterable[Any], model_name: str = "llama3.1") -> None:
        super().__init__(list(tools), model_name=model_name)

    def _create_agent(self):  # type: ignore[override]
        template = (
            "You are Remote SysCheck AI, a professional assistant for remote infrastructure management.\n\n"
            "You manage legitimate administration tasks (Java/Tomcat install, health checks, resource audits) over SSH or PowerShell.\n"
            "Never attempt destructive or irreversible changes unless the user explicitly confirms.\n\n"
            "Available tools:\n{tools}\n\n"
            "Follow the ReAct format:\n"
            "Question: the input question\n"
            "Thought: consider required data\n"
            "Action: tool name from [{tool_names}]\n"
            "Action Input: JSON parameters (use {{}} if none)\n"
            "Observation: tool result\n"
            "... (repeat Thought/Action/Observation)\n"
            "Thought: I have the information needed\n"
            "Final Answer: provide a concise, technical summary\n\n"
            "Always specify server identifiers and parameter keys exactly as defined by the tools.\n"
            "Use explicit JSON for Action Input (e.g., {{\"server\": \"demo\"}}).\n\n"
            "Question: {input}\nThought:{agent_scratchpad}"
        )

        prompt = PromptTemplate(
            input_variables=["input", "agent_scratchpad"],
            partial_variables={
                "tools": "\n".join([f"{tool.name}: {tool.description}" for tool in self.langchain_tools]),
                "tool_names": ", ".join([tool.name for tool in self.langchain_tools]),
            },
            template=template,
        )

        return create_react_agent(
            llm=self.llm,
            tools=self.langchain_tools,
            prompt=prompt,
        )
