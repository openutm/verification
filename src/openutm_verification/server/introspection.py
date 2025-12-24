import inspect
import re
from enum import Enum
from typing import Any, Dict, Type

from openutm_verification.core.execution.dependency_resolution import DEPENDENCIES


def _get_type_info(annotation: Any) -> tuple[str, bool, list[dict[str, Any]] | None]:
    """Extracts type string, enum status, and options from an annotation."""
    type_str = "Any"
    is_enum = False
    options = None

    if annotation != inspect.Parameter.empty:
        if inspect.isclass(annotation) and issubclass(annotation, Enum):
            is_enum = True
            type_str = annotation.__name__
            options = [{"name": e.name, "value": e.value} for e in annotation]
        else:
            type_str = str(annotation)
            # Use regex to remove module paths
            type_str = re.sub(r"([a-zA-Z_]\w*\.)+", "", type_str)
            # Remove <class '...'> wrapper if present
            if type_str.startswith("<class '") and type_str.endswith("'>"):
                type_str = type_str[8:-2]

    return type_str, is_enum, options


def _get_default_value(default: Any) -> Any:
    """Extracts the default value for a parameter."""
    if default == inspect.Parameter.empty:
        return None
    if default is None:
        return None
    if isinstance(default, Enum):
        return default.value
    return str(default)


def process_parameter(param_name: str, param: inspect.Parameter) -> Dict[str, Any] | None:
    """
    Extracts metadata from a function parameter for API generation.
    """
    if param_name == "self":
        return None

    type_str, is_enum, options = _get_type_info(param.annotation)
    default_val = _get_default_value(param.default)

    param_info = {
        "name": param_name,
        "type": type_str,
        "default": default_val,
        "required": param.default == inspect.Parameter.empty,
    }

    if is_enum:
        param_info["isEnum"] = True
        param_info["options"] = options

    return param_info


def process_method(class_name: str, client_class: Type, name: str, method: Any) -> Dict[str, Any] | None:
    """
    Extracts metadata from a client method if it's a scenario step.
    """
    if not hasattr(method, "_is_scenario_step"):
        return None

    step_name = getattr(method, "_step_name")
    sig = inspect.signature(method)
    parameters = []
    for param_name, param in sig.parameters.items():
        # Skip dependencies that are automatically injected
        if param.annotation in DEPENDENCIES:
            continue

        param_info = process_parameter(param_name, param)
        if param_info:
            parameters.append(param_info)

    return {
        "id": f"{class_name}.{name}",
        "name": step_name,
        "functionName": name,
        "className": class_name,
        "description": inspect.getdoc(method) or "",
        "parameters": parameters,
        "filePath": inspect.getfile(client_class),
    }
