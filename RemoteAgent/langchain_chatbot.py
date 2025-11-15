"""Compatibility shim for the removed RemoteLangChainChatBot module."""

from __future__ import annotations


raise ImportError(
    "RemoteAgent.langchain_chatbot has been removed. "
    "Use RemoteAgent.chatbot.RemoteWorkflowChatBot instead."
)
