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
├─ Remote/                   # Remote orchestration (YAML + INI driven)
│  ├─ config/                # settings.yaml + servers.ini
│  ├─ install/               # RemoteTomcatInstallTool
│  ├─ pre_install/           # RemoteJavaInstallTool
│  ├─ post_install/          # RemoteTomcatPostInstallTool
│  ├─ utilities/             # Shared helpers (download/extract, config loading)
│  └─ run_remote_workflow.py # CLI runner for multi-host execution
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

The same workflow is exposed through the chatbot as the `remote_workflow` tool. Ask
SysCheck AI to run it (optionally overriding `settings_path`, `servers_path`, or
`target_servers`) to execute remote provisioning conversationally.
