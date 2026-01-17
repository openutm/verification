import inspect
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import Any, AsyncContextManager, AsyncGenerator, Callable, ContextManager, Coroutine, Generator, TypeVar, cast
from unittest.mock import Mock

from pydantic import ConfigDict, validate_call

from openutm_verification.core.execution.config_models import RunContext

T = TypeVar("T")


DEPENDENCIES: dict[object, Callable[..., ContextManager[object] | AsyncContextManager[object]]] = {}
CONTEXT: ContextVar[RunContext] = ContextVar(
    "context",
    default=cast(
        RunContext,
        {"scenario_id": "", "suite_scenario": None, "suite_name": None, "docs": None},
    ),
)


def dependency(type: object) -> Callable:
    def wrapper(func: Callable[..., Generator | AsyncGenerator]) -> Callable[..., Generator | AsyncGenerator]:
        if inspect.isasyncgenfunction(func):
            DEPENDENCIES[type] = asynccontextmanager(func)
        else:
            DEPENDENCIES[type] = contextmanager(func)  # type: ignore
        return func

    return wrapper


class DependencyResolver:
    """Resolves dependencies using a provided ExitStack."""

    def __init__(self, stack: AsyncExitStack):
        self.stack = stack
        self._cache: dict[object, object] = {}

    async def resolve(self, type_: object) -> object:
        """Resolve a dependency of a specific type."""
        if type_ in self._cache:
            return self._cache[type_]

        if type_ not in DEPENDENCIES:
            raise ValueError(f"No dependency registered for type {type_}")

        dependency_func = DEPENDENCIES[type_]
        sig = inspect.signature(dependency_func)

        # Resolve dependencies of this dependency
        dep_args = []
        for param in sig.parameters.values():
            if param.annotation is not inspect.Parameter.empty and param.annotation is not type(None):
                dep_instance = await self.resolve(param.annotation)
                dep_args.append(dep_instance)

        cm = dependency_func(*dep_args)
        if hasattr(cm, "__aenter__"):
            # cast to AsyncContextManager to satisfy type checker
            instance = await self.stack.enter_async_context(cast(AsyncContextManager, cm))
        else:
            # cast to ContextManager to satisfy type checker
            instance = self.stack.enter_context(cast(ContextManager, cm))

        self._cache[type_] = instance
        return instance


@asynccontextmanager
async def provide(*types: object) -> AsyncGenerator[tuple[object, ...], None]:
    """Context manager to provide dependencies for the given types.

    This function recursively resolves dependencies, meaning if a dependency
    function requires other dependencies as parameters, they will be automatically
    provided.

    Args:
        *types: The types of dependencies to provide.
    Yields:
        All the requested dependencies as a tuple.
    """
    async with AsyncExitStack() as stack:
        resolver = DependencyResolver(stack)
        instances = []
        for t in types:
            instances.append(await resolver.resolve(t))
        yield tuple(instances)


async def call_with_dependencies(func: Callable[..., Coroutine[Any, Any, T]], resolver: DependencyResolver | None = None, **kwargs: Any) -> T:
    """Call a function with its dependencies automatically provided.

    Args:
        func: The function to call.
        resolver: Optional DependencyResolver to use. If None, a new one is created.
        **kwargs: Additional arguments to pass to the function.
    Returns:
        The result of the function call.
    """
    if resolver:
        sig = inspect.signature(func)
        call_kwargs = kwargs.copy()

        for name, param in sig.parameters.items():
            if name in call_kwargs:
                continue

            if param.annotation in DEPENDENCIES:
                call_kwargs[name] = await resolver.resolve(param.annotation)

        if inspect.iscoroutinefunction(func):
            if isinstance(func, Mock):
                validated_func = func
            else:
                validated_func = validate_call(func, config=ConfigDict(arbitrary_types_allowed=True))  # type: ignore
            return await validated_func(**call_kwargs)
        raise ValueError(f"Function {func.__name__} must be async")
    else:
        async with AsyncExitStack() as stack:
            temp_resolver = DependencyResolver(stack)
            return await call_with_dependencies(func, resolver=temp_resolver, **kwargs)
