import os
import datetime
import difflib
import json
import re
from typing import Dict, Any, List, Tuple

import requests

# --- Ollama helper functions -----------------------------------------------
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.1"


def call_ollama_chat(messages: List[Dict[str, str]],
                      model: str = OLLAMA_MODEL,
                      stream: bool = True,
                      timeout: int = 120) -> Tuple[str, List[Dict[str, Any]]]:
    # print(messages)
    payload = {"model": model, "messages": messages, "stream": stream}
    try:
        resp = requests.post(OLLAMA_URL, json=payload, stream=stream, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Failed to contact Ollama at {OLLAMA_URL}: {e}")

    chunks: List[Dict[str, Any]] = []
    reply = ""

    if stream:
        for raw in resp.iter_lines():
            if not raw:
                continue
            try:
                chunk = json.loads(raw.decode("utf-8"))
            except Exception:
                chunk = {"raw": raw.decode("utf-8", errors="replace")}
            chunks.append(chunk)
            msg = chunk.get("message")
            if isinstance(msg, dict) and "content" in msg:
                reply += msg["content"]
            if chunk.get("done"):
                break
    else:
        text = resp.text
        try:
            data = resp.json()
            chunks.append(data)
            if isinstance(data, dict) and "message" in data and "content" in data["message"]:
                reply = data["message"]["content"]
            else:
                reply = text
        except ValueError:
            reply = text
            chunks.append({"raw": text})

    return reply, chunks


# --- ChatBot (minimal changes; no extract_json helper) ---------------------
class ChatBot:
    def __init__(self, tools: List[Any]):
        self.tools = {tool.name: tool for tool in tools}
        self.conversation_history: List[Dict[str, str]] = []
        self.persona = f"""
            You are SysCheck AI, a professional system readiness assistant.

            Never perform destructive actions.  

            Keep tone technical, direct, and professional.


            Tools and parameter schemas (USE THESE EXACT KEYS):
            {chr(10).join([str(tool.get_info()) for tool in tools])}

            You MUST follow the exact parameter names for all the tools as given in the tool descriptions.

            NOTE: Only use the tools that are needed for the task at hand.
            """.strip() 

    def perform_task(self, user_input: str) -> str:
        conversation_str = "\n".join(
            [f"User: {msg['user']}\nBot: {msg['bot']}" for msg in self.conversation_history]
        )
        prompt = f"""
User Request: {user_input}

Previous conversation:
{conversation_str}

Analyze the request and respond with VALID JSON ONLY:

For simple queries (Only: Greetings, farewells) that do NOT require tools:
{{
    "TaskType": "Simple",
    "Response": "your direct answer here"
}}

For complex tasks requiring tools:
{{
    "TaskType": "Complex",
    "ActionsNeeded": "Step-by-step plan: First use tool_name with parameters X, then use tool_name2 with parameters Y"
}}

For Tasks which needs tools that are not listed above, respond with:
{{
    "TaskType": "incompatible",
    "Response": "I'm sorry, but I do not have the necessary tools to complete this request."
}}
RULES:
- Return ONLY valid JSON (no markdown, no code blocks, no extra text)
- Do NOT use Python syntax like tuples ()
- For ActionsNeeded, write a clear text description of steps
- Use tools only when It is absolutely needed by the query"""

        messages = [{"role": "system", "content": self.persona}, {"role": "user", "content": prompt}]
        reply_text, _ = call_ollama_chat(messages)
        print("----"*15)
        print("Model Response:\n", reply_text)
        print("----"*15)
        return self.complete_tasks(reply_text)

    def complete_tasks(self, response_text: str) -> str:
        # Pre-process: Convert Python tuple syntax to JSON arrays if present
        # Replace (...) with [...] for ActionsNeeded arrays
        cleaned_text = re.sub(r'\(([^)]+)\)', r'[\1]', response_text)
        
        try:
            # Directly parse JSON returned by model
            json_response_data = json.loads(cleaned_text)
            task_type = json_response_data.get("TaskType")
            if task_type == "Simple" or task_type == "incompatible":
                return json_response_data.get("Response")

            elif task_type == "Complex":
                return self.execute_complex_workflow(json_response_data)
            else:
                return "Unrecognized TaskType in model response."
        except json.JSONDecodeError as e:
            # If the model returned additional text around JSON, try to extract {...} first
            try:
                m = re.search(r"(\{.*\})", response_text, flags=re.DOTALL)
                if m:
                    # Apply the same tuple-to-array conversion
                    extracted = re.sub(r'\(([^)]+)\)', r'[\1]', m.group(1))
                    json_response_data = json.loads(extracted)
                    task_type = json_response_data.get("TaskType")
                    if task_type == "Simple":
                        return json_response_data.get("Response", "I couldn't process your request.")
                    elif task_type == "Complex":
                        return self.execute_complex_workflow(json_response_data)
                # else fallthrough to error
            except Exception:
                pass
            # Model returned non-JSON text. Log and return the raw text as a friendly fallback.
            print(f"JSON parsing error: {e}")
            print(f"Raw response: {response_text}")
            # Return the raw response_text as a fallback so CLI doesn't show an internal error to the user
            return response_text.strip()

    def execute_complex_workflow(self, initial_response: Dict[str, Any]) -> str:
        actions_needed = initial_response.get("ActionsNeeded", "")
        tool_execution_log = ""

        workflow_prompt_template = f"""
Task Plan: {actions_needed}

Available tools:
{chr(10).join([str(tool.get_info()) for tool in self.tools.values()])}

Already Executed:
{{tool_execution_log}}

CRITICAL: Review the execution log above. If the task is ALREADY COMPLETE, return taskStatus="completed".

Return VALID JSON for the NEXT action:

To execute a tool:
{{
    "taskStatus": "inprogress",
    "tool": "exact_tool_name",
    "parameters": {{"param_name": value}},
    "reasoning": "what this accomplishes"
}}

When task is complete:
{{
    "taskStatus": "completed",
    "tool": "none",
    "parameters": {{}},
    "reasoning": "all required steps done"
}}

RULES:
- Check execution log FIRST - never repeat a tool that already ran successfully
- If the original task is answered by existing log entries, mark as completed
- Return ONLY valid JSON (no extra text)
- Use exact tool/parameter names from descriptions""".strip()

        step_count = 0
        max_steps = 10

        while step_count < max_steps:
            step_count += 1
            print(f"\n--- Step {step_count} ---")
            workflow_prompt = workflow_prompt_template.replace("{tool_execution_log}", tool_execution_log)
            messages = [{"role": "system", "content": self.persona}, {"role": "user", "content": workflow_prompt}]
            step_text, _ = call_ollama_chat(messages)
            print(f"Step Response: {step_text}")

            try:
                step_data = json.loads(step_text)
                task_status = step_data.get("taskStatus", "")
                tool_name = step_data.get("tool", "none")
                parameters = step_data.get("parameters", {})
                reasoning = step_data.get("reasoning", "")

                print(f"Task Status: {task_status}")
                print(f"Tool: {tool_name}")
                print(f"Parameters: {parameters}")
                print(f"Reasoning: {reasoning}")

                if (not task_status) or (task_status.lower() == "completed") or (tool_name == "none"):
                    print("Workflow completed!")
                    final_prompt = f"""
Based on the following task execution log, provide a nice, conclusive response to the user:

Original Task: {actions_needed}

Execution Log:
{tool_execution_log}

Provide a friendly summary of what was accomplished.
"""
                    final_messages = [{"role": "system", "content": self.persona}, {"role": "user", "content": final_prompt}]
                    final_text, _ = call_ollama_chat(final_messages)
                    return final_text

                if task_status.lower() == "inprogress" and tool_name in self.tools:
                    try:
                        tool_result = self.tools[tool_name].run(**parameters)
                        tool_execution_log += f"\nStep {step_count}: Executed {tool_name} with {parameters}\nResult: {tool_result}\n"
                        print(f"Tool Result: {tool_result}")
                    except Exception as e:
                        tool_execution_log += f"\nStep {step_count}: Error executing {tool_name}: {e}\n"
                        print(f"Tool execution error: {e}")
                elif task_status.lower() == "inprogress" and tool_name not in self.tools:
                    print(f"Tool '{tool_name}' not found in available tools: {list(self.tools.keys())}")
                    break

            except json.JSONDecodeError as e:
                # try to extract {...} if model wrapped JSON
                try:
                    m = re.search(r"(\{.*\})", step_text, flags=re.DOTALL)
                    if m:
                        step_data = json.loads(m.group(1))
                        # repeat same handling (simple approach: continue loop and let next iteration process)
                        continue
                except Exception:
                    pass

                print(f"Error parsing step response JSON: {e}")
                print(f"Raw step response: {step_text}")
                break
            except ValueError as e:
                print(f"Error extracting JSON: {e}")
                print(f"Raw step response: {step_text}")
                break

        return f"I attempted to complete the task but reached the maximum number of steps. Here's what was accomplished:\n{tool_execution_log}"
