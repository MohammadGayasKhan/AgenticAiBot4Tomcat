import datetime
from typing import List, Any, Dict, Optional
from langchain_ollama import ChatOllama
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field


class LangChainChatBot:
    """ChatBot using LangChain for better orchestration and workflow management"""
    
    def __init__(self, tools: List[Any], model_name: str = "llama3.1"):
        self.model_name = model_name
        self.llm = ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=0.1,
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
            early_stopping_method="generate"
        )
        
        self.conversation_history = []
    
    def _convert_tools(self, tools: List[Any]) -> List[StructuredTool]:
        """Convert custom tool objects to LangChain StructuredTool format"""
        langchain_tools = []
        
        for tool in tools:
            tool_info = tool.get_info()
            
            def create_tool_func(t):
                """Closure to capture the tool instance"""
                def tool_func(**kwargs) -> str:
                    """Execute the tool and return formatted result"""
                    try:
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
                            return f"Status: {status}\n{output}\n{details}"
                        return str(result)
                    except Exception as e:
                        return f"Error executing {t.name}: {str(e)}"
                return tool_func
            
            # Create the args schema dynamically based on tool parameters
            args_schema_fields = {}
            tool_params = tool_info.get('parameters', {})
            
            # Handle empty list (no parameters)
            if isinstance(tool_params, list) and len(tool_params) == 0:
                tool_params = {}
            
            if isinstance(tool_params, dict) and len(tool_params) > 0:
                for param_name, param_info in tool_params.items():
                    if isinstance(param_info, dict):
                        param_type = param_info.get('type', 'str')
                        param_desc = param_info.get('description', '')
                        
                        # Map type strings to Python types
                        type_map = {
                            'int': int,
                            'str': str,
                            'list': List[int],
                            'list of int': List[int],
                            'float': float,
                            'bool': bool
                        }
                        python_type = type_map.get(param_type, str)
                        
                        args_schema_fields[param_name] = (python_type, Field(description=param_desc))
                    else:
                        # Simple string parameter definition like "list of int"
                        param_str = str(param_info).lower()
                        if 'list' in param_str:
                            python_type = List[int]
                        elif 'int' in param_str:
                            python_type = int
                        else:
                            python_type = str
                        
                        args_schema_fields[param_name] = (python_type, Field(description=param_str))
            
            # Create a Pydantic model for this tool's arguments
            if args_schema_fields:
                ArgsSchema = type(f"{tool.name}_args", (BaseModel,), {
                    '__annotations__': {k: v[0] for k, v in args_schema_fields.items()},
                    **{k: v[1] for k, v in args_schema_fields.items()}
                })
            else:
                # No parameters - create empty schema
                ArgsSchema = None
            
            langchain_tool = StructuredTool(
                name=tool.name,
                description=tool_info.get('description', ''),
                func=create_tool_func(tool),
                args_schema=ArgsSchema
            )
            langchain_tools.append(langchain_tool)
        
        return langchain_tools
    
    def _create_agent(self):
        """Create a LangChain agent with proper prompting"""
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are SysCheck AI, a professional system readiness assistant.

Current date and time: {datetime}

Your role:
- Help users check system readiness (Java, disk space, ports, etc.)
- Use tools when needed to gather information
- Provide clear, technical, and direct responses
- Never perform destructive actions

When using tools:
- Call them with exact parameter names as specified
- One tool at a time
- Analyze results before deciding next steps
- Stop when you have the answer to the user's question

Remember: Only use tools when necessary. If you can answer directly, do so."""),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        agent = create_tool_calling_agent(
            llm=self.llm,
            tools=self.langchain_tools,
            prompt=prompt
        )
        
        return agent
    
    def chat(self, user_input: str) -> str:
        """Process a user query and return the response"""
        try:
            # Prepare input with datetime
            current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Invoke the agent
            result = self.agent_executor.invoke({
                "input": user_input,
                "datetime": current_time,
                "chat_history": self._get_chat_history()
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
