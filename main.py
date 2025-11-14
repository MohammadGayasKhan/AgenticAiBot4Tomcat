## CLI Based ChatBot Application

from chatbot import ChatBot
from Tools.pre_requisit_check.check_disk import CheckDisk
from Tools.pre_requisit_check.check_java import CheckJava
from Tools.pre_requisit_check.check_ports import CheckPorts
from Tools.Installation.tomcat_start import StartTomcat
from Tools.post_install.tomcat_post_install import PostInstallTomcat
from Tools.remote_workflow_tool import RemoteWorkflowTool


if __name__ == "__main__":
    disk_tool = CheckDisk()
    java_tool = CheckJava()
    ports_tool = CheckPorts()
    tomcat_start_tool = StartTomcat()
    tomcat_post_install_tool = PostInstallTomcat()
    remote_workflow_tool = RemoteWorkflowTool()

    chatbot = ChatBot(
        tools=[
            disk_tool,
            java_tool,
            ports_tool,
            tomcat_start_tool,
            tomcat_post_install_tool,
            remote_workflow_tool,
        ]
    )
    try:
        while True:
            try:
                user_input = input("You: ")
            except EOFError:
                # Input stream closed (e.g., pipe ended). Exit gracefully.
                print("\nInput closed. Exiting chat. Goodbye!")
                break

            if not user_input:
                # empty line -> prompt again
                continue

            if user_input.lower() in ["exit", "quit"]:
                print("Exiting chat. Goodbye!")
                break

            response = chatbot.perform_task(user_input)
            print(f"Bot: {response}")
    except KeyboardInterrupt:
        print("\nInterrupted. Exiting chat. Goodbye!")