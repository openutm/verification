from typing import Any, Type, TypeVar

from fastapi import APIRouter, Depends, Request

from openutm_verification.core.execution.definitions import StepDefinition

T = TypeVar("T")

scenario_router = APIRouter()


def get_runner(request: Request) -> Any:
    return request.app.state.runner


def get_dependency(dep_type: Type[T]):
    async def dependency(runner: Any = Depends(get_runner)) -> T:
        # Ensure session is initialized
        if not runner.session_resolver:
            await runner.initialize_session()
        return await runner.session_resolver.resolve(dep_type)

    return dependency


@scenario_router.post("/api/step")
async def execute_step(step: StepDefinition, runner: Any = Depends(get_runner)):
    return await runner.execute_single_step(step)
