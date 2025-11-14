from typing import Dict, Any


class RemoteTool:
    """Base class for all remote orchestration tools."""

    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name = name
        self.description = description
        self.parameters = parameters

    def get_info(self) -> Dict[str, Any]:
        return {
            "toolName": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def run(self, *args, **kwargs):
        raise NotImplementedError("Remote tools must implement run()")
