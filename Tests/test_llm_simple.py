"""
Simple test to see if LLM can invoke a single tool
"""

import sys
import os

# Add current directory to path
sys.path.append(os.path.dirname(__file__))

from chatbot_langchain import LangChainChatBot
from Tools.pre_requisit_check.check_ports import CheckPorts

def main():
    print("Testing LLM tool invocation...")
    print("="*70)
    
    # Create chatbot with just the port checker tool
    tools = [CheckPorts()]
    chatbot = LangChainChatBot(tools)
    
    # Very simple, direct command
    query = "check port 8080"
    print(f"\nQuery: {query}\n")
    
    response = chatbot.chat(query)
    print(f"\nFinal Response: {response}\n")
    print("="*70)

if __name__ == "__main__":
    main()
