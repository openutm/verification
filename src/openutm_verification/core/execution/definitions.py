from typing import Any, Dict, List
from uuid import uuid4

from pydantic import BaseModel, Field


class StepDefinition(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    parameters: Dict[str, Any]
    run_in_background: bool = False


class ScenarioDefinition(BaseModel):
    steps: List[StepDefinition]
