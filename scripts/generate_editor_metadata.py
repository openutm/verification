import ast
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


def parse_type_annotation(annotation: Any) -> str:
    """Helper to convert AST type annotation to string representation."""
    if annotation is None:
        return "Any"
    if isinstance(annotation, ast.Name):
        return annotation.id
    elif isinstance(annotation, ast.Subscript):
        value = parse_type_annotation(annotation.value)
        slice_val = parse_type_annotation(annotation.slice)
        return f"{value}[{slice_val}]"
    elif isinstance(annotation, ast.Constant):
        return str(annotation.value)
    elif isinstance(annotation, ast.Attribute):
        return annotation.attr
    elif isinstance(annotation, ast.BinOp):
        # Handle Union types like str | int
        left = parse_type_annotation(annotation.left)
        right = parse_type_annotation(annotation.right)
        return f"{left} | {right}"
    return "Any"


def parse_default_value(node: Any) -> Any:
    """Helper to convert AST default value to python object."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{parse_default_value(node.value)}.{node.attr}"
    # Handle other types if necessary
    return str(node)


def get_step_name_from_decorator(decorator: Any) -> Optional[str]:
    if isinstance(decorator, ast.Call):
        func = decorator.func
        is_scenario_step = False
        if isinstance(func, ast.Name) and func.id == "scenario_step":
            is_scenario_step = True
        elif isinstance(func, ast.Attribute) and func.attr == "scenario_step":
            is_scenario_step = True

        if is_scenario_step and decorator.args:
            arg = decorator.args[0]
            if isinstance(arg, ast.Constant):
                return str(arg.value)
            # Handle older python versions or string literals
            elif isinstance(arg, ast.Str):
                return str(arg.s)
    elif isinstance(decorator, ast.Name) and decorator.id == "scenario_step":
        return "Scenario Step"
    return None


def extract_enums(file_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    """Extract Enum definitions from a file."""
    enums = {}
    if not file_path.exists():
        return enums

    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError:
            return enums

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            is_enum = False
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id == "Enum":
                    is_enum = True
                elif isinstance(base, ast.Attribute) and base.attr == "Enum":
                    is_enum = True

            if is_enum:
                values = []
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                # We found an enum member
                                name = target.id
                                value = None
                                if isinstance(item.value, ast.Constant):
                                    value = item.value.value
                                elif isinstance(item.value, ast.Str):  # Python < 3.8
                                    value = item.value.s
                                elif isinstance(item.value, ast.Num):  # Python < 3.8
                                    value = item.value.n

                                if value is not None:
                                    values.append({"name": name, "value": value})
                enums[node.name] = values
    return enums


def extract_args(function_node: Union[ast.FunctionDef, ast.AsyncFunctionDef], known_enums: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    args = []

    # Calculate defaults mapping
    defaults = function_node.args.defaults
    # defaults correspond to the last n arguments
    args_with_defaults = function_node.args.args[-len(defaults) :] if defaults else []
    default_map = {}
    for arg, default in zip(args_with_defaults, defaults):
        default_map[arg.arg] = parse_default_value(default)

    for arg in function_node.args.args:
        if arg.arg == "self":
            continue

        arg_type = parse_type_annotation(arg.annotation)
        arg_data = {"name": arg.arg, "type": arg_type}

        if arg.arg in default_map:
            arg_data["default"] = default_map[arg.arg]

        if arg_type in known_enums:
            arg_data["options"] = known_enums[arg_type]
            arg_data["isEnum"] = True

        args.append(arg_data)
    return args


def process_class_node(class_node: ast.ClassDef, file_path_str: str, known_enums: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    steps = []
    class_name = class_node.name
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            step_name = None
            # Check decorators
            for decorator in item.decorator_list:
                step_name = get_step_name_from_decorator(decorator)
                if step_name:
                    break

            if step_name:
                args = extract_args(item, known_enums)
                docstring = ast.get_docstring(item)

                steps.append(
                    {
                        "id": f"{class_name}.{item.name}",
                        "name": step_name,
                        "functionName": item.name,
                        "className": class_name,
                        "description": docstring,
                        "parameters": args,
                        "filePath": file_path_str,
                    }
                )
    return steps


def extract_scenario_steps(file_path: Path, project_root: Path, known_enums: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            tree = ast.parse(f.read(), filename=str(file_path))
        except SyntaxError:
            print(f"Syntax error in {file_path}")
            return []

    try:
        relative_path = file_path.relative_to(project_root)
    except ValueError:
        relative_path = file_path

    steps = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            steps.extend(process_class_node(node, str(relative_path), known_enums))
    return steps


def main():
    # Resolve paths relative to the script location
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    base_dir = project_root / "src/openutm_verification/core/clients"
    models_file = project_root / "src/openutm_verification/models.py"
    output_file = project_root / "web-editor/src/data/operations.json"

    # Extract Enums first
    print(f"Extracting enums from {models_file}...")
    known_enums = extract_enums(models_file)
    print(f"Found enums: {list(known_enums.keys())}")

    all_steps = []

    for root, _, files in os.walk(base_dir):
        for file in files:
            if file.endswith(".py") and not file.startswith("__"):
                file_path = Path(root) / file
                print(f"Processing {file_path}...")
                steps = extract_scenario_steps(file_path, project_root, known_enums)
                all_steps.extend(steps)

    print(f"Found {len(all_steps)} scenario steps.")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_steps, f, indent=2)

    print(f"Written metadata to {output_file}")


if __name__ == "__main__":
    main()
