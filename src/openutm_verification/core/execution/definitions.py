from typing import Any, Dict, List

from pydantic import BaseModel, Field


class LoopConfig(BaseModel):
    """Configuration for step looping."""

    model_config = {"populate_by_name": True}

    count: int | None = Field(default=None, description="Number of times to repeat (fixed iteration)")
    items: List[Any] | None = Field(default=None, description="List of items to iterate over")
    while_condition: str | None = Field(default=None, alias="while", description="Condition to continue looping")


class StepDefinition(BaseModel):
    model_config = {"populate_by_name": True}

    id: str | None = Field(default=None, description="Unique identifier for the step. If not provided, it defaults to the step name.")
    step: str = Field(..., description="The operation/function to execute (human-readable name) or group name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the operation")
    needs: List[str] = Field(default_factory=list, description="List of step IDs this step depends on")
    background: bool = Field(default=False, description="Whether to run this step in the background")
    description: str | None = None
    if_condition: str | None = Field(default=None, alias="if", description="Conditional expression to determine if step should run")
    loop: LoopConfig | None = Field(default=None, description="Loop configuration for repeating the step")


class GroupDefinition(BaseModel):
    """Definition of a reusable group of steps."""

    description: str | None = None
    steps: List[StepDefinition] = Field(..., description="Steps that make up this group")


class ScenarioDefinition(BaseModel):
    name: str
    description: str | None = None
    groups: Dict[str, GroupDefinition] = Field(default_factory=dict, description="Named groups of steps that can be referenced")
    steps: List[StepDefinition]
