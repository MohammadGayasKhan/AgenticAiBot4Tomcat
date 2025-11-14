from typing import Dict, Any


class Tool:
    """
    Base class for all pre-installation tools.

    Subclasses must implement run() and return a dictionary with:
        name, status, command, output, details
    """
    def __init__(self, name: str, description: str, parameters=None):
        self.name: str = name
        self.description: str = description
        self.parameters = parameters or []

    def get_info(self) -> Dict[str, Any]:
        return {
            "toolName": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def run(self) -> Dict[str, Any]:
        """Must be implemented by subclasses."""
        raise NotImplementedError
