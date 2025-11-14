# AgenticAiBot4Tomcat
 

A developer-friendly repo that runs Tomcat readiness checks, installation steps, and post-install verification — all driven via an agentic chatbot interface.
The chatbot orchestrates modular "tools" that inspect the system (Java, disk, RAM, ports), optionally perform safe install steps, and verify results — so you can run everything conversationally, locally, and reproducibly.

# Key features

Conversational interface (CLI chatbot or local LLM) to run checks and guide installation.

Modular checks: each check is a Tool class under prerequit tool/.

Orchestrator dynamically discovers and runs tools, aggregates results. 

Human-friendly output

# Structure (high-level)

```
AgenticAiBot4Tomcat/
├─ Tools/
│  ├─ pre_requisit_check/    # Local prerequisite checks
│  ├─ Installation/          # Local install / start / stop tools
│  └─ post_install/          # Local post-install validation
│
├─ Remote/                   # Remote orchestration primitives (YAML + INI driven)
│  ├─ config/                # settings.yaml + servers.ini
│  ├─ install/               # RemoteTomcatInstallTool
│  ├─ pre_install/           # Remote resource checks + Java install tools
│  ├─ post_install/          # RemoteTomcatPostInstallTool
│  ├─ utilities/             # Shared helpers (download/extract, config loading)
│  └─ run_remote_workflow.py # Legacy CLI runner for multi-host execution
│
├─ RemoteAgent/              # Standalone remote chatbot project (dynamic tools)
│  ├─ chatbot.py             # CLI chatbot wrapper with auto-discovered tools
│  ├─ langchain_chatbot.py   # LangChain variant of the remote chatbot
│  ├─ tool_loader.py         # Discovers Remote.* tool classes automatically
│  ├─ dynamic_adapter.py     # Connects tools with config + remote execution
│  ├─ main.py                # CLI entry point (non-LangChain)
│  └─ main_langchain.py      # CLI entry point (LangChain / ReAct agent)
│
├─ chatbot.py                # CLI chatbot orchestrator (local tools)
├─ main.py / main_langchain.py
├─ requirements.txt
└─ README.md
```

# Remote automation

The `Remote/` package lets you execute the full Java → Tomcat install → post-install
validation pipeline across one or more hosts via SSH. Everything is data-driven:

- `Remote/config/settings.yaml` defines install metadata (URLs, paths, commands).
- `Remote/config/servers.ini` defines the target hosts, credentials, or key paths.
- `Remote/run_remote_workflow.py` ties it together and runs the workflow per host.

Example usage (run from repository root):

```powershell
python -m Remote.run_remote_workflow --settings Remote/config/settings.yaml --servers Remote/config/servers.ini
```

> Tip: adjust the YAML to match your desired Tomcat/Java versions, directories,
> and start/stop commands. Set usernames/passwords or SSH keys in the INI file.

Every tool returns structured dictionaries (`status`, `details`, `output`, etc.) so
you can log results or feed them into higher-level automation.

# Remote chatbot project

All remote automation tooling is now accessible via a dedicated chatbot project in
`RemoteAgent/`. Tools are discovered dynamically: dropping a new module under the
`Remote` package (e.g., `Remote/custom/remote_db_backup.py`) that defines a
`RemoteTool` subclass makes it immediately available to the chatbot without adding
any registration code.

Run the remote chatbot via the LangChain ReAct agent:

```powershell
python -m RemoteAgent.main_langchain
```

The agent automatically loads `settings.yaml` / `servers.ini` by default and exposes
the same parameter schema the tools advertise. Override paths or inject ad-hoc hosts
at runtime by passing JSON arguments when the bot calls tools (e.g., set
`host`/`username` directly in the tool invocation prompt).

Use the `list_servers` tool to inspect the configured inventory without providing a
specific host.

The legacy `remote_workflow` tool remains available for scripted multi-host runs,
but the chatbot can now process bespoke sequences by chaining individual tools at
runtime — no pre-defined workflow is required.

# Manual remote test scripts

For shell-based validation of each remote tool (outside the chatbot), use the scripts in
`Remote/tests_manual/`. Example:

```powershell
python Remote/tests_manual/disk_check.py --server server.example1
python Remote/tests_manual/port_check.py --server server.example1 --ports 8080 8005 8009
python Remote/tests_manual/ram_check.py --server server.example1
python Remote/tests_manual/java_install.py --server server.example1
python Remote/tests_manual/tomcat_install.py --server server.example1
python Remote/tests_manual/tomcat_start.py --server server.example1 --tomcat-home "C:\\temp\\tomcat_test\\apache-tomcat-10.1.34"
python Remote/tests_manual/tomcat_validate.py --server server.example1 --tomcat-home "C:\\temp\\tomcat_test\\apache-tomcat-10.1.34"
python Remote/tests_manual/tomcat_stop.py --server server.example1 --tomcat-home "C:\\temp\\tomcat_test\\apache-tomcat-10.1.34"
python Remote/tests_manual/tomcat_post_install.py --server server.example1 --tomcat-home "C:\\temp\\tomcat_test\\apache-tomcat-10.1.34"
python Remote/tests_manual/tomcat_uninstall.py --server server.example1 --tomcat-home "C:\\temp\\tomcat_test\\apache-tomcat-10.1.34"
```

Each script accepts `--settings` / `--servers` overrides if you keep configuration files elsewhere.
The Tomcat post-install script orchestrates start, HTTP validation, and stop commands; use
`--skip-start` or `--skip-stop` to tailor the sequence.
