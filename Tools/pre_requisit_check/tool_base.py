from typing import Dict, Any


class Tool:
    """Base class for all prerequisite check tools.

    Subclasses must implement run() and return a dictionary with the required
    keys described in the project requirements.
    """
    def __init__(self, name, description, parameters):
        self.name: str = name
        self.description: str = description
        self.parameters: dict = parameters

    def get_info(self) -> Dict[str, Any]:
        return {
            "toolName": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def run(self):
        raise NotImplementedError
