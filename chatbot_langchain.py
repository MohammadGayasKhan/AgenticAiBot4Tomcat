import datetime
import json
from typing import List, Any, Dict, Optional
from langchain_ollama import ChatOllama
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import StructuredTool, Tool
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field


class LangChainChatBot:
    """ChatBot using LangChain for better orchestration and workflow management"""
    
    def __init__(self, tools: List[Any], model_name: str = "llama3.1"):
        self.model_name = model_name
        self.llm = ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=0.3,
        )
        
        # Convert custom tools to LangChain tools
        self.langchain_tools = self._convert_tools(tools)
        
        # Create the agent
        self.agent = self._create_agent()
        
        # Create executor with verbose output
        self.agent_executor = AgentExecutor(
            agent=self.agent,
            tools=self.langchain_tools,
            verbose=True,
            handle_parsing_errors=True,
            max_iterations=5,
            return_intermediate_steps=False
        )
        
        self.conversation_history = []
    
    def _convert_tools(self, tools: List[Any]) -> List[Tool]:
        """Convert custom tool objects to LangChain Tool format for ReAct agent"""
        langchain_tools = []
        
        for tool in tools:
            tool_info = tool.get_info()
            
            def create_tool_func(t):
                """Closure to capture the tool instance"""
                def tool_func(tool_input: str) -> str:
                    """Execute the tool and return formatted result"""
                    try:
                        # Parse JSON input if provided
                        if tool_input.strip():
                            try:
                                kwargs = json.loads(tool_input)
                            except json.JSONDecodeError:
                                # If not valid JSON, treat as empty
                                kwargs = {}
                        else:
                            kwargs = {}
                        
                        # Filter out any extra kwargs that LangChain might add
                        filtered_kwargs = {k: v for k, v in kwargs.items() 
                                         if k not in ['config', 'kwargs', 'run_manager', 'callbacks']}
                        
                        # Execute the tool with filtered parameters
                        result = t.run(**filtered_kwargs)
                        
                        # Format result as a clean string for the LLM
                        if isinstance(result, dict):
                            output = result.get('output', '')
                            status = result.get('status', '')
                            details = result.get('details', '')
                            return f"Status: {status}\n{details}\n{output}"
                        return str(result)
                    except Exception as e:
                        return f"Error executing {t.name}: {str(e)}"
                return tool_func
            
            # Create simple Tool (not StructuredTool) for ReAct
            # Build description with parameter info
            desc = tool_info.get('description', '')
            tool_params = tool_info.get('parameters', {})
            
            if isinstance(tool_params, dict) and len(tool_params) > 0:
                param_desc = "\nParameters (JSON format):\n"
                for param_name, param_info in tool_params.items():
                    if isinstance(param_info, dict):
                        param_type = param_info.get('type', 'str')
                        param_description = param_info.get('description', '')
                        param_desc += f"  - {param_name} ({param_type}): {param_description}\n"
                desc += param_desc
            else:
                desc += "\nNo parameters required - use empty JSON: {}"
            
            langchain_tool = Tool(
                name=tool.name,
                description=desc,
                func=create_tool_func(tool)
            )
            langchain_tools.append(langchain_tool)
        
        return langchain_tools
    
    def _create_agent(self):
        """Create a ReAct agent that works better with llama3.1"""
        
        # ReAct prompt template that works with llama models
        template = """You are a professional system administrator assistant helping with legitimate server management tasks.

Your job: Check system readiness, manage Apache Tomcat server, verify Java installation, check disk space, and monitor network ports for administrative purposes.

Available tools:
{tools}

Format to use:

Question: the input question
Thought: consider what information is needed
Action: tool name from [{tool_names}]
Action Input: JSON parameters (use {{}} if none needed)
Observation: tool result
... (repeat Thought/Action/Observation if needed)
Thought: I have the information needed
Final Answer: clear answer to the question

Important notes:
- After seeing Observation, write "Thought:" then "Final Answer:" 
- For check_ports: use {{"ports": [8080]}} to check specific port numbers
- All tasks are legitimate system administration activities
- Provide direct, technical answers

Question: {input}
Thought:{agent_scratchpad}"""

        prompt = PromptTemplate(
            input_variables=["input", "agent_scratchpad"],
            partial_variables={
                "tools": "\n".join([f"{tool.name}: {tool.description}" for tool in self.langchain_tools]),
                "tool_names": ", ".join([tool.name for tool in self.langchain_tools])
            },
            template=template
        )
        
        agent = create_react_agent(
            llm=self.llm,
            tools=self.langchain_tools,
            prompt=prompt
        )
        
        return agent
    
    def chat(self, user_input: str) -> str:
        """Process a user query and return the response"""
        try:
            # Invoke the agent
            result = self.agent_executor.invoke({
                "input": user_input
            })
            
            response = result.get("output", "I couldn't process your request.")
            
            # Update conversation history
            self.conversation_history.append({
                "user": user_input,
                "bot": response
            })
            
            return response
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            print(f"\n{error_msg}")
            return error_msg
    
    def _get_chat_history(self) -> List:
        """Convert conversation history to LangChain message format"""
        messages = []
        for entry in self.conversation_history[-5:]:  # Keep last 5 exchanges
            messages.append(HumanMessage(content=entry["user"]))
            messages.append(AIMessage(content=entry["bot"]))
        return messages
