# AgenticAiBot4Tomcat
 

A developer-friendly repo that runs Tomcat readiness checks, installation steps, and post-install verification — all driven via an agentic chatbot interface.
The chatbot orchestrates modular "tools" that inspect the system (Java, disk, RAM, ports), optionally perform safe install steps, and verify results — so you can run everything conversationally, locally, and reproducibly.

# Key features

Conversational interface (CLI chatbot or local LLM) to run checks and guide installation.

Modular checks: each check is a Tool class under prerequit tool/.

Orchestrator dynamically discovers and runs tools, aggregates results. 

Human-friendly output

# Structure(Modified accordingly)

AgenticAiBot4Tomcat/
│
├─ prerequit tool/                         # Pre-installation system readiness checks
│  ├─ tool_base.py                         # Base Tool class interface (defines run() contract)
│  ├─ check_java.py                        # Checks Java installation, version & JAVA_HOME
│  ├─ check_disk.py                        # Checks available disk space
│  ├─ check_ram.py                         # Checks total system RAM
│  └─ check_ports.py                       # Checks Tomcat default ports (8080, 8005, 8009)
│
├─ installation/   
|  └─ modified accordingly
│
├─ PostValidation/                          
│  └─ modified accordingly
│
├─ chatbot.py                               # Central orchestrator: runs tools, chat interface
│                                           # Coordinates pre-check, install, and post-check logic
│
├─ requirements.txt                         
├─ README.md                               
└─ .gitignore                              
