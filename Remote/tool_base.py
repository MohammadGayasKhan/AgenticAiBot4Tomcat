from typing import Dict, Any, Tuple


class RemoteTool:
    """Base class for all remote orchestration tools."""

    # Default configuration scope within settings.yaml (e.g., ("pre_install", "java"))
    config_path: Tuple[str, ...] = ()

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        user_parameters: Dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.user_parameters = user_parameters or {}

    def get_info(self) -> Dict[str, Any]:
        return {
            "toolName": self.name,
            "description": self.description,
            "parameters": self.user_parameters or self.parameters,
        }

    def get_config_path(self) -> Tuple[str, ...]:
        return self.config_path

    def get_user_parameters(self) -> Dict[str, Any]:
        return self.user_parameters or self.parameters

    def run(self, *args, **kwargs):
        raise NotImplementedError("Remote tools must implement run()")
