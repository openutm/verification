import inspect
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import Any, AsyncContextManager, AsyncGenerator, Callable, ContextManager, Coroutine, Generator, TypeVar, cast

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


async def call_with_dependencies(func: Callable[..., Coroutine[Any, Any, T]]) -> T:
    """Call a function with its dependencies automatically provided.

    Args:
        func: The function to call.
    Returns:
        The result of the function call.
    """
    sig = inspect.signature(func)
    async with provide(*(p.annotation for p in sig.parameters.values())) as dependencies:
        if inspect.iscoroutinefunction(func):
            return await func(*dependencies)
        raise ValueError(f"Function {func.__name__} must be async")


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
