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
├─ RemoteAgent/              # Standalone remote chatbot project (LangChain)
│  ├─ chatbot.py             # RemoteWorkflowChatBot (LangChain + workflow orchestration)
│  ├─ inventory_tool.py      # Optional helper to list configured servers
│  ├─ main.py                # Compatibility shim (redirects users to LangChain entry point)
│  └─ main_langchain.py      # CLI entry point for the LangChain workflow bot
│
├─ main_langchain.py         # Convenience wrapper around RemoteAgent.main_langchain
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

Remote automation now flows through a single LangChain-powered bot: `RemoteWorkflowChatBot`
(`RemoteAgent/chatbot.py`). The bot keeps conversation context, remembers prior
selections, and delegates the heavy lifting to the `remote_workflow` tool so every
server runs the full Java → Tomcat workflow sequentially.

Run the chatbot with optional overrides for config paths or the Ollama model name:

```powershell
python -m RemoteAgent.main_langchain --settings Remote/config/settings.yaml --servers Remote/config/servers.ini
```

Key behaviour:
- **Session memory:** The bot replays the latest history (last ~12 turns) to keep answers consistent.
- **Smart server selection:** If only one server is configured it runs immediately. When multiple servers exist it asks whether to act on a specific host or "all". Once you pick, that choice is remembered until you change it.
- **Workflow per server:** Every selected host runs the entire provisioning and validation workflow independently, and the bot summarizes the combined results.
- **No premature stops:** The chat loop only aborts if the user gives conflicting/invalid server choices several times in a row; otherwise it finishes the job regardless of intermediate step counts.

The underlying `Tools/remote_workflow_tool.py` is still available for scripted usage or tests, so you can automate the same flow without the conversational layer when needed.

## Remote agent quickstart checklist

1. **Install dependencies** (inside a virtual environment if desired):
	```powershell
	pip install -r requirements.txt
	```
2. **Configure settings** in `Remote/config/settings.yaml` (download URLs, install paths, Tomcat start/stop commands). Make sure `post_install.default_tomcat_home` matches the real deploy directory.
3. **Define servers** in `Remote/config/servers.ini` with `host`, `username`, and either `password` or `key_path`. Optionally add per-server overrides such as `tomcat_home`.
4. **Launch the chatbot** and talk to it:
	```powershell
	python -m RemoteAgent.main_langchain --settings Remote/config/settings.yaml --servers Remote/config/servers.ini
	```
	Example prompts:
	- `check disk space on server.example1`
	- `run all prerequisites on both servers`
	- `install tomcat on server.example2`
	- `stop tomcat` / `uninstall tomcat` / `validate tomcat`

	The bot decides which remote tools to call, streams a concise summary, and writes detailed traces to `logs/remote_chatbot.log`.
5. **Review logs** if something fails. Every tool emits structured JSON so you can trace SSH commands, stdout/stderr, and follow-up suggestions.

> Tip: When running against real infrastructure, keep your Ollama / LangChain model on the same machine where these tools run so the agent can launch SSH sessions locally.

## Enabling OpenSSH on Windows targets

Remote execution requires an SSH service on each Windows host. Run these commands **as Administrator on the target machine**:

1. Download OpenSSH from the official release page and extract it:
	- Download: [OpenSSH-Win64.zip](https://github.com/PowerShell/Win32-OpenSSH/releases)
	- Extract to: `C:\Program Files\OpenSSH`

2. Install and register the SSH service:
	```powershell
	cd "C:\Program Files\OpenSSH"
	powershell.exe -ExecutionPolicy Bypass -File install-sshd.ps1
	```

3. Allow inbound SSH through Windows Firewall:
	```powershell
	New-NetFirewallRule -Name sshd -DisplayName "OpenSSH Server" -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
	```

4. Start the service and set it to launch automatically:
	```powershell
	Start-Service sshd
	Set-Service sshd -StartupType Automatic
	```

5. (Optional) Validate from another machine:
	```powershell
	ssh username@192.168.x.x
	```

Replace `username` and the IP with the actual account configured in `servers.ini`. Once SSH succeeds from your automation host, the remote chatbot can run all prerequisite checks and Tomcat workflows without additional setup.

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
