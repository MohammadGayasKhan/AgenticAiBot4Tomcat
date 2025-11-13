## CLI Based ChatBot Application with LangChain

from chatbot_langchain import LangChainChatBot
from Tools.pre_requisit_check.check_disk import CheckDisk
from Tools.pre_requisit_check.check_java import CheckJava
from Tools.pre_requisit_check.check_ports import CheckPorts
from Tools.Installation.tomcat_install import InstallTomcat
from Tools.Installation.tomcat_uninstall import UninstallTomcat



if __name__ == "__main__":
    print("Initializing SysCheck AI with LangChain...\n")
    
    # Initialize tools
    disk_tool = CheckDisk()
    java_tool = CheckJava()
    ports_tool = CheckPorts()
    tomcat_install_tool = InstallTomcat()
    tomcat_uninstall_tool = UninstallTomcat()
    
    # Create LangChain-powered chatbot
    chatbot = LangChainChatBot(
        tools=[disk_tool, java_tool, ports_tool, tomcat_install_tool, tomcat_uninstall_tool],
        model_name="llama3.1"
    )
    
    print("SysCheck AI is ready! Type 'quit' or 'exit' to stop.\n")
    
    try:
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                print("\nInput closed. Exiting chat. Goodbye!")
                break
            
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit", "bye"]:
                print("Exiting chat. Goodbye!")
                break
            
            # Process with LangChain agent
            print()  # Add blank line for readability
            response = chatbot.chat(user_input)
            print(f"\nBot: {response}\n")
            
    except KeyboardInterrupt:
        print("\n\nInterrupted. Exiting chat. Goodbye!")
