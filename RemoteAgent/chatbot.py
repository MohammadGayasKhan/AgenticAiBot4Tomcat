"""LangChain-enabled chatbot that lets the LLM plan dynamic remote workflows."""

from __future__ import annotations

import inspect
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import Runnable, RunnableLambda
from langchain_ollama import ChatOllama

from Remote.install.remote_tomcat_install import RemoteTomcatInstallTool
from Remote.install.remote_tomcat_uninstall import RemoteTomcatUninstallTool
from Remote.post_install.tomcat_start import RemoteTomcatStartTool
from Remote.post_install.tomcat_stop import RemoteTomcatStopTool
from Remote.post_install.tomcat_validation import RemoteTomcatValidationTool
from Remote.pre_install.remote_disk_check import RemoteDiskCheckTool
from Remote.pre_install.remote_java_install import RemoteJavaInstallTool
from Remote.pre_install.remote_port_check import RemotePortCheckTool
from Remote.pre_install.remote_ram_check import RemoteRamCheckTool
from Remote.remote_executor import RemoteExecutor
from Remote.utilities.config_loader import load_server_ini, load_yaml
from RemoteAgent.inventory_tool import ServerInventoryTool
from Tools.remote_workflow_tool import RemoteWorkflowTool

DEFAULT_SETTINGS_PATH = "Remote/config/settings.yaml"
DEFAULT_SERVERS_PATH = "Remote/config/servers.ini"
MAX_HISTORY_MESSAGES = 12
MAX_SELECTION_ATTEMPTS = 3
ALL_KEYWORDS = ("all", "every", "entire", "both")
LOG_FILE = Path("logs/remote_chatbot.log")
KEYWORD_TOOL_SEQUENCES = [
    (("disk", "storage"), ["remote_disk_check"]),
    (("ram", "memory"), ["remote_ram_check"]),
    (("port", "ports"), ["remote_port_check"]),
    (("prereq", "prerequisite", "pre-req"), [
        "remote_disk_check",
        "remote_ram_check",
        "remote_java_install",
        "remote_port_check",
    ]),
    (("java",), ["remote_java_install"]),
    (("uninstall", "remove"), ["remote_tomcat_stop", "remote_tomcat_uninstall"]),
    (("start",), ["remote_tomcat_start"]),
    (("stop", "shutdown"), ["remote_tomcat_stop"]),
    (("validate", "validation", "health"), ["remote_tomcat_validation"]),
    (("workflow",), ["remote_workflow"]),
    (("install", "setup", "deploy"), [
        "remote_disk_check",
        "remote_ram_check",
        "remote_java_install",
        "remote_port_check",
        "remote_tomcat_install",
        "remote_tomcat_start",
        "remote_tomcat_validation",
    ]),
]


class RemoteWorkflowChatBot:
    """Conversational agent that lets the LLM build per-request tool workflows."""

    def __init__(
        self,
        *,
        model_name: str = "llama3.1",
        temperature: float = 0.2,
        settings_path: str = DEFAULT_SETTINGS_PATH,
        servers_path: str = DEFAULT_SERVERS_PATH,
        workflow_tool: Optional[RemoteWorkflowTool] = None,
        llm_client: Optional[ChatOllama] = None,
        server_inventory: Optional[Sequence[Dict[str, Any]]] = None,
        log_path: Path | str = LOG_FILE,
    ) -> None:
        self.settings_path = settings_path
        self.servers_path = servers_path
        self.workflow_tool = workflow_tool or RemoteWorkflowTool()
        raw_llm = llm_client or ChatOllama(
            model=model_name,
            base_url="http://localhost:11434",
            temperature=temperature,
        )
        self._llm = self._coerce_llm(raw_llm)
        self._server_override = [dict(entry) for entry in server_inventory] if server_inventory else None
        self.history: List[BaseMessage] = []
        self.awaiting_server_choice = False
        self.pending_request: Optional[str] = None
        self.presented_servers: Optional[List[Dict[str, Any]]] = None
        self.selection_attempts = 0
        self.active_servers: Optional[List[Dict[str, Any]]] = None

        self._logger = self._configure_logger(log_path)
        self._adapters = self._build_tool_adapters()
        self._selection_chain = self._build_selection_chain()
        self._planner_chain = self._build_planner_chain()
        self._summary_chain = self._build_summary_chain()

    def chat(self, user_input: str) -> str:
        """Process user input and let the LLM drive an execution plan."""

        user_text = (user_input or "").strip()
        if not user_text:
            return "Please provide a request."

        self._logger.info("USER: %s", user_text)
        self._append_history("human", user_text)
        servers = self._load_servers()
        if not servers:
            message = (
                "I could not find any servers in the inventory. "
                "Update Remote/config/servers.ini and try again."
            )
            self._append_history("ai", message)
            self._logger.info("BOT: %s", message)
            return message

        if self.awaiting_server_choice:
            presented = self.presented_servers or servers
            selection = self._parse_server_selection(user_text, presented)
            if selection:
                response = self._plan_and_execute(
                    original_request=self.pending_request or user_text,
                    latest_user_input=user_text,
                    selection=selection,
                )
                self._append_history("ai", response)
                self._logger.info("BOT: %s", response)
                self._reset_selection_state(selection)
                return response
            retry = self._handle_selection_retry(presented)
            self._logger.info("BOT: %s", retry)
            return retry

        selection = self._detect_servers_in_text(user_text, servers)
        if not selection:
            selection = self._match_active_servers(servers)
        if not selection:
            if len(servers) == 1:
                selection = [servers[0]]
            else:
                self.awaiting_server_choice = True
                self.pending_request = user_text
                self.presented_servers = list(servers)
                self.selection_attempts = 0
                prompt = self._ask_for_selection(user_text, servers)
                self._append_history("ai", prompt)
                self._logger.info("BOT: %s", prompt)
                return prompt

        response = self._plan_and_execute(
            original_request=user_text,
            latest_user_input=user_text,
            selection=selection,
        )
        self._append_history("ai", response)
        self._logger.info("BOT: %s", response)
        self._reset_selection_state(selection)
        return response

    def _plan_and_execute(
        self,
        *,
        original_request: str,
        latest_user_input: str,
        selection: Sequence[Dict[str, Any]],
    ) -> str:
        identifiers = [self._server_identifier(server) for server in selection]
        plan_text = self._generate_plan(original_request, identifiers)
        execution_records = self._execute_plan(plan_text, selection)
        payload = {
            "history": self._history_tail(),
            "request": original_request,
            "selected_servers": ", ".join(identifiers) or "n/a",
            "latest_user_input": latest_user_input,
            "plan": plan_text,
            "execution_summary": json.dumps(execution_records, indent=2),
        }
        response = self._summary_chain.invoke(payload)
        self.active_servers = list(selection)
        return response

    def _generate_plan(self, request: str, identifiers: Sequence[str]) -> str:
        keyword_plan = self._keyword_plan(request)
        if keyword_plan:
            plan_text = json.dumps(keyword_plan)
            self._logger.info("PLAN (keyword): %s", plan_text)
            return plan_text
        payload = {
            "history": self._history_tail(),
            "request": request,
            "selected_servers": ", ".join(identifiers),
            "tool_reference": self._tool_reference_text(),
        }
        plan_text = self._planner_chain.invoke(payload)
        if not plan_text.strip():
            plan_text = json.dumps(self._default_plan(request, identifiers))
        self._logger.info("PLAN: %s", plan_text)
        return plan_text

    def _execute_plan(
        self,
        plan_text: str,
        selection: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        try:
            parsed = json.loads(plan_text)
        except json.JSONDecodeError:
            parsed = self._default_plan(
                plan_text, [self._server_identifier(server) for server in selection]
            )

        tasks = parsed.get("tasks") if isinstance(parsed, dict) else None
        if not isinstance(tasks, list) or not tasks:
            tasks = self._default_plan(
                plan_text, [self._server_identifier(server) for server in selection]
            )["tasks"]

        selection_map = {
            self._server_identifier(server): server for server in selection
        }
        records: List[Dict[str, Any]] = []

        for entry in tasks:
            if not isinstance(entry, dict):
                continue
            tool_name = entry.get("tool")
            if not tool_name:
                continue
            targets = self._resolve_task_targets(entry.get("server"), selection_map)
            params = entry.get("params") if isinstance(entry.get("params"), dict) else {}
            adapter = self._adapters.get(tool_name)
            if not adapter:
                for identifier in targets:
                    records.append(
                        {
                            "tool": tool_name,
                            "server": identifier,
                            "status": "Failed",
                            "details": "Tool not available in this environment.",
                        }
                    )
                continue

            for identifier in targets:
                try:
                    result = adapter.run(identifier, dict(params))
                except Exception as exc:  # pragma: no cover - defensive guard
                    result = {
                        "status": "Failed",
                        "details": str(exc),
                    }
                result = self._post_process_result(tool_name, result)
                records.append(
                    {
                        "tool": tool_name,
                        "server": identifier,
                        "status": result.get("status", "Unknown"),
                        "details": result.get("details"),
                        "result": result,
                    }
                )
        self._logger.info("EXECUTION: %s", json.dumps(records, indent=2))
        return records

    def _post_process_result(self, tool_name: str, result: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name == "remote_tomcat_stop" and result.get("status") == "Failed":
            details = (result.get("details") or "").lower()
            tolerated = (
                "connection refused" in details
                or "not running" in details
                or "not listening" in details
                or "already stopped" in details
            )
            if tolerated:
                updated = dict(result)
                updated["status"] = "Skipped"
                updated.setdefault("details", "Tomcat already stopped; skipping shutdown.")
                return updated
        return result

    def _resolve_task_targets(
        self,
        target_descriptor: Any,
        selection_map: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        identifiers = list(selection_map.keys())
        if not target_descriptor:
            return identifiers
        if isinstance(target_descriptor, str) and target_descriptor.strip().lower() in {"all", "*"}:
            return identifiers

        targets: List[str] = []
        if isinstance(target_descriptor, str):
            tokens = [token.strip() for token in target_descriptor.split(",") if token.strip()]
        elif isinstance(target_descriptor, list):
            tokens = [str(token).strip() for token in target_descriptor if str(token).strip()]
        else:
            tokens = []

        for token in tokens:
            lowered = token.lower()
            for identifier in identifiers:
                if identifier.lower() == lowered:
                    targets.append(identifier)
                    break
        return targets or identifiers

    def _default_plan(self, request: str, identifiers: Sequence[str]) -> Dict[str, Any]:
        keyword_plan = self._keyword_plan(request)
        if keyword_plan:
            return keyword_plan
        return {
            "tasks": [
                {"tool": "remote_workflow", "server": "all", "params": {}}
            ],
            "notes": "Generated fallback plan",
        }

    def _keyword_plan(self, request: str) -> Optional[Dict[str, Any]]:
        normalized = (request or "").lower()
        if not normalized:
            return None

        matched_tools: List[str] = []

        def append_tool(tool_name: str) -> None:
            if tool_name not in matched_tools:
                matched_tools.append(tool_name)

        for keywords, sequence in KEYWORD_TOOL_SEQUENCES:
            if any(self._keyword_matches(normalized, keyword) for keyword in keywords):
                for tool_name in sequence:
                    append_tool(tool_name)

        if not matched_tools:
            return None

        tasks = [
            {"tool": tool_name, "server": "all", "params": {}}
            for tool_name in matched_tools
        ]
        return {"tasks": tasks, "notes": "keyword-plan"}

    def _keyword_matches(self, text: str, keyword: str) -> bool:
        token = keyword.strip().lower()
        if not token:
            return False
        if re.fullmatch(r"[a-z0-9]+", token):
            pattern = rf"\b{re.escape(token)}\b"
            return re.search(pattern, text) is not None
        return token in text

    def _tool_reference_text(self) -> str:
        parts = []
        for adapter in self._adapters.values():
            parts.append(f"- {adapter.name}: {adapter.description}")
        return "\n".join(parts)

    def _build_tool_adapters(self) -> Dict[str, "RemoteToolAdapter"]:
        adapters = [
            RemoteToolAdapter(RemoteDiskCheckTool(), self.settings_path, self.servers_path, self._logger),
            RemoteToolAdapter(RemoteRamCheckTool(), self.settings_path, self.servers_path, self._logger),
            RemoteToolAdapter(RemotePortCheckTool(), self.settings_path, self.servers_path, self._logger),
            RemoteToolAdapter(RemoteJavaInstallTool(), self.settings_path, self.servers_path, self._logger),
            RemoteToolAdapter(RemoteTomcatInstallTool(), self.settings_path, self.servers_path, self._logger),
            RemoteToolAdapter(RemoteTomcatUninstallTool(), self.settings_path, self.servers_path, self._logger),
            RemoteToolAdapter(RemoteTomcatStartTool(), self.settings_path, self.servers_path, self._logger),
            RemoteToolAdapter(RemoteTomcatStopTool(), self.settings_path, self.servers_path, self._logger),
            RemoteToolAdapter(RemoteTomcatValidationTool(), self.settings_path, self.servers_path, self._logger),
            RemoteToolAdapter(self.workflow_tool, self.settings_path, self.servers_path, self._logger),
            InventoryToolAdapter(
                ServerInventoryTool(), self.settings_path, self.servers_path, self._logger
            ),
        ]
        return {adapter.name: adapter for adapter in adapters}

    def _build_planner_chain(self):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are Remote Workflow Planner. Decide which remote tools to run and their order. "
                    "Always express plans as JSON with keys 'tasks' (list) and 'notes'. Each task must have 'tool', 'server', and 'params'. "
                    "Use only the listed tools. Pick the smallest set of tools that satisfies the user's request; "
                    "do NOT schedule Tomcat install/start/validation when the user only asked for checks or uninstalls.",
                ),
                MessagesPlaceholder("history"),
                (
                    "human",
                    "Workflow Plan Request:\n"
                    "Original request: {request}\n"
                    "Selected servers: {selected_servers}\n"
                    "Available tools:\n{tool_reference}\n"
                    "Return compact JSON only.",
                ),
            ]
        )
        return prompt | self._llm | StrOutputParser()

    def _build_summary_chain(self):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are Remote Workflow AI. Summarize executed tasks, highlight successes/failures, and recommend follow-ups.",
                ),
                MessagesPlaceholder("history"),
                (
                    "human",
                    "Execution Summary Request:\n"
                    "Original request: {request}\n"
                    "Selected servers: {selected_servers}\n"
                    "Plan JSON: {plan}\n"
                    "Execution results: {execution_summary}\n"
                    "Latest user input: {latest_user_input}\n"
                    "Respond with a concise report.",
                ),
            ]
        )
        return prompt | self._llm | StrOutputParser()

    def _ask_for_selection(self, request: str, servers: Sequence[Dict[str, Any]]) -> str:
        server_lines = [
            f"{index + 1}. {self._server_label(server)}" for index, server in enumerate(servers)
        ]
        payload = {
            "history": self._history_tail(),
            "request": request,
            "servers": "\n".join(server_lines),
        }
        return self._selection_chain.invoke(payload)

    def _build_selection_chain(self):
        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are Remote Workflow AI. Ask the user which servers to target when several are available."
                    " Offer numbered options and mention the 'all servers' choice.",
                ),
                MessagesPlaceholder("history"),
                (
                    "human",
                    "Original request: {request}\nServer options:\n{servers}\nAsk for numbered selections.",
                ),
            ]
        )
        return prompt | self._llm | StrOutputParser()

    def _handle_selection_retry(self, servers: Sequence[Dict[str, Any]]) -> str:
        self.selection_attempts += 1
        if self.selection_attempts >= MAX_SELECTION_ATTEMPTS:
            message = (
                "I was unable to understand the server selection after multiple tries. "
                "Please start over with a new request."
            )
            self._reset_selection_state(None)
            self._append_history("ai", message)
            return message

        request = self.pending_request or "the previous task"
        prompt = self._ask_for_selection(request, servers)
        self._append_history("ai", prompt)
        return prompt

    def _load_servers(self) -> List[Dict[str, Any]]:
        if self._server_override is not None:
            return [dict(entry) for entry in self._server_override]
        try:
            return load_server_ini(self.servers_path)
        except FileNotFoundError:
            return []
        except Exception:
            return []

    def _detect_servers_in_text(
        self, text: str, servers: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        normalized = text.lower()
        if self._mentions_all(normalized):
            return list(servers)

        matches: List[Dict[str, Any]] = []
        for server in servers:
            identifiers = self._server_identifiers(server)
            if any(identifier and identifier in normalized for identifier in identifiers):
                matches.append(server)
        return self._dedupe_servers(matches)

    def _parse_server_selection(
        self, text: str, servers: Sequence[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not servers:
            return []
        normalized = text.strip().lower()
        if not normalized:
            return []
        if self._mentions_all(normalized):
            return list(servers)

        matches: List[Dict[str, Any]] = []
        for match in re.findall(r"\d+", normalized):
            index = int(match) - 1
            if 0 <= index < len(servers):
                matches.append(servers[index])

        tokens = re.split(r"[\s,;]+", normalized)
        for token in tokens:
            for server in servers:
                identifiers = self._server_identifiers(server)
                if any(identifier == token for identifier in identifiers if identifier):
                    matches.append(server)
                    break

        if not matches:
            for server in servers:
                identifiers = self._server_identifiers(server)
                if any(identifier and identifier in normalized for identifier in identifiers):
                    matches.append(server)
        return self._dedupe_servers(matches)

    def _match_active_servers(self, servers: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.active_servers:
            return []
        active_ids = {self._server_identifier(server) for server in self.active_servers}
        return [server for server in servers if self._server_identifier(server) in active_ids]

    def _reset_selection_state(self, selection: Optional[Sequence[Dict[str, Any]]]) -> None:
        if selection:
            self.active_servers = list(selection)
        self.awaiting_server_choice = False
        self.pending_request = None
        self.presented_servers = None
        self.selection_attempts = 0

    def _server_label(self, server: Dict[str, Any]) -> str:
        name = str(server.get("name") or server.get("host") or "unknown").strip()
        host = str(server.get("host") or "").strip()
        return f"{name} ({host})" if host and host != name else name

    def _server_identifier(self, server: Dict[str, Any]) -> str:
        name = str(server.get("name") or "").strip()
        host = str(server.get("host") or "").strip()
        return name or host or "unknown"

    def _server_identifiers(self, server: Dict[str, Any]) -> List[str]:
        identifiers = []
        name = str(server.get("name") or "").strip().lower()
        host = str(server.get("host") or "").strip().lower()
        if name:
            identifiers.append(name)
        if host and host not in identifiers:
            identifiers.append(host)
        return identifiers

    def _mentions_all(self, text: str) -> bool:
        return any(re.search(rf"\b{keyword}\b", text) for keyword in ALL_KEYWORDS)

    def _dedupe_servers(self, servers: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for server in servers:
            identifier = self._server_identifier(server)
            if identifier not in seen:
                seen.add(identifier)
                unique.append(server)
        return unique

    def _append_history(self, role: str, content: str) -> None:
        if role == "human":
            self.history.append(HumanMessage(content=content))
        else:
            self.history.append(AIMessage(content=content))
        if len(self.history) > MAX_HISTORY_MESSAGES:
            self.history = self.history[-MAX_HISTORY_MESSAGES:]

    def _history_tail(self) -> List[BaseMessage]:
        return list(self.history[-MAX_HISTORY_MESSAGES:])

    def _configure_logger(self, log_path: Path | str) -> logging.Logger:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger("remote_workflow_chatbot")
        if not logger.handlers:
            handler = logging.FileHandler(path, encoding="utf-8")
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
            logger.propagate = False
        return logger

    def _coerce_llm(self, client: Any) -> Runnable:
        if isinstance(client, Runnable):
            return client

        if hasattr(client, "invoke") and callable(client.invoke):
            return RunnableLambda(
                lambda input_, **kwargs: client.invoke(self._normalize_llm_input(input_), **kwargs)
            )

        if callable(client):
            return RunnableLambda(
                lambda input_, **kwargs: client(self._normalize_llm_input(input_), **kwargs)
            )

        raise TypeError("llm_client must be a LangChain Runnable, callable, or expose invoke().")

    def _normalize_llm_input(self, value: Any) -> Any:
        if hasattr(value, "messages"):
            try:
                return value.messages
            except Exception:
                pass
        return value


class RemoteToolAdapter:
    """Adapter that turns RemoteTool classes into executable steps."""

    def __init__(
        self,
        tool: Any,
        settings_path: str,
        servers_path: str,
        logger: logging.Logger,
    ) -> None:
        self.tool = tool
        self.name = tool.name
        self.description = tool.description
        self.settings_path = settings_path
        self.servers_path = servers_path
        self.logger = logger
        self.is_workflow = isinstance(tool, RemoteWorkflowTool)
        self._run_signature = inspect.signature(tool.run)
        self._accepts_kwargs = any(
            param.kind == inspect.Parameter.VAR_KEYWORD
            for param in self._run_signature.parameters.values()
        )

    def run(self, server_identifier: Optional[str], params: Dict[str, Any]) -> Dict[str, Any]:
        local_params = dict(params or {})
        settings_path = local_params.pop("settings_path", self.settings_path)
        servers_path = local_params.pop("servers_path", self.servers_path)

        if self.is_workflow:
            targets = local_params.get("target_servers")
            if not targets:
                targets = [server_identifier] if server_identifier else None
            result = self.tool.run(
                settings_path=settings_path,
                servers_path=servers_path,
                target_servers=targets,
            )
            self.logger.info("TOOL %s -> %s", self.name, result.get("status"))
            return result

        try:
            servers = self._load_servers(servers_path)
        except Exception as exc:
            return {"status": "Failed", "details": str(exc)}
        if not server_identifier:
            return {"status": "Failed", "details": "No server specified for tool execution."}
        server_info = self._select_server(servers, server_identifier)
        if not server_info:
            return {
                "status": "Failed",
                "details": f"Server '{server_identifier}' not found in inventory {servers_path}.",
            }

        host = local_params.pop("host", server_info.get("host"))
        username = local_params.pop("username", server_info.get("username"))
        password = local_params.pop("password", server_info.get("password")) or None
        key_path = local_params.pop("key_path", server_info.get("key_path")) or None

        executor = RemoteExecutor(host=host, username=username, password=password, key_path=key_path)
        try:
            executor.connect()
            settings = load_yaml(settings_path)
            config = self._resolve_config(settings, self.tool)
            call_kwargs = dict(local_params)
            call_kwargs.setdefault("executor", executor)
            call_kwargs.setdefault("config", config)
            if self._allows_argument("server") and server_info is not None:
                call_kwargs.setdefault("server", server_info)
            if self._allows_argument("tomcat_home"):
                default_home = self._lookup_default_tomcat_home(settings)
                call_kwargs.setdefault(
                    "tomcat_home",
                    (server_info or {}).get("tomcat_home") or default_home,
                )
            result = self.tool.run(**call_kwargs)
        except Exception as exc:
            self.logger.error("TOOL %s failed: %s", self.name, exc)
            return {
                "status": "Failed",
                "details": str(exc),
            }
        finally:
            try:
                executor.close()
            except Exception:
                pass
        result.setdefault("target_server", server_info.get("name", server_identifier))
        self.logger.info(
            "TOOL %s on %s -> %s",
            self.name,
            server_info.get("name", server_identifier),
            result.get("status"),
        )
        return result

    def _load_servers(self, servers_path: str) -> List[Dict[str, Any]]:
        try:
            return load_server_ini(servers_path)
        except Exception as exc:
            raise ValueError(f"Unable to read servers file {servers_path}: {exc}") from exc

    def _allows_argument(self, name: str) -> bool:
        if name in self._run_signature.parameters:
            return True
        return self._accepts_kwargs

    def _lookup_default_tomcat_home(self, settings: Dict[str, Any]) -> Optional[str]:
        post_install = settings.get("post_install") if isinstance(settings, dict) else None
        if isinstance(post_install, dict):
            value = post_install.get("default_tomcat_home")
            if isinstance(value, str) and value.strip():
                return value.strip()
        install = settings.get("install") if isinstance(settings, dict) else None
        if isinstance(install, dict):
            tomcat = install.get("tomcat")
            if isinstance(tomcat, dict):
                windows_cfg = tomcat.get("windows")
                if isinstance(windows_cfg, dict):
                    candidate = windows_cfg.get("install_root")
                    if isinstance(candidate, str) and candidate.strip():
                        return candidate.strip()
        return None

    def _select_server(
        self, servers: Sequence[Dict[str, Any]], identifier: str
    ) -> Optional[Dict[str, Any]]:
        normalized = identifier.strip().lower()
        for record in servers:
            name = str(record.get("name", "")).strip().lower()
            host = str(record.get("host", "")).strip().lower()
            if normalized in {name, host}:
                return dict(record)
        return None

    def _resolve_config(self, settings: Dict[str, Any], tool: Any) -> Dict[str, Any]:
        path = getattr(tool, "config_path", ())
        cursor: Any = settings
        for key in path:
            if not isinstance(cursor, dict):
                return {}
            cursor = cursor.get(key, {})
        return cursor if isinstance(cursor, dict) else {}


class InventoryToolAdapter(RemoteToolAdapter):
    """Adapter for ServerInventoryTool (no SSH connection)."""

    def __init__(
        self,
        tool: ServerInventoryTool,
        settings_path: str,
        servers_path: str,
        logger: logging.Logger,
    ) -> None:
        super().__init__(tool, settings_path, servers_path, logger)

    def run(self, server_identifier: Optional[str], params: Dict[str, Any]) -> Dict[str, Any]:
        local_params = dict(params or {})
        servers_path = local_params.get("servers_path", self.servers_path)
        result = self.tool.run(servers_path=servers_path)
        self.logger.info("TOOL %s -> %s", self.name, result.get("status"))
        return result


__all__ = ["RemoteWorkflowChatBot"]
