from typing import Dict, Any


class Tool:
    """Base class for all post-installation tools.

    Subclasses must implement run() and return a dictionary that includes the
    keys described in the project requirements (status, command, output,
    details, etc.).
    """

    def __init__(self, name: str, description: str, parameters: Dict[str, Any]):
        self.name: str = name
        self.description: str = description
        self.parameters: Dict[str, Any] = parameters

    def get_info(self) -> Dict[str, Any]:
        return {
            "toolName": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def run(self, *args, **kwargs):
        raise NotImplementedError
