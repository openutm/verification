import importlib
from pathlib import Path

# Get the path to the current directory
scenarios_path = Path(__file__).parent

# Dynamically import all modules matching 'test_*.py'
# This ensures that the @register_scenario decorator in each file is executed.
for file in scenarios_path.glob("test_*.py"):
    module_name = f"openutm_verification.scenarios.{file.stem}"
    importlib.import_module(module_name)
