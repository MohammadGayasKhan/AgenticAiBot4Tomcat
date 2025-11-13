from Tools.pre_requisit_check.check_disk import CheckDisk
from Tools.pre_requisit_check.check_java import CheckJava
from Tools.pre_requisit_check.check_ports import CheckPorts

disk_tool = CheckDisk()
java_tool = CheckJava()
ports_tool = CheckPorts()

print("CheckDisk info:", disk_tool.get_info())
print("\nCheckJava info:", java_tool.get_info())
print("\nCheckPorts info:", ports_tool.get_info())
