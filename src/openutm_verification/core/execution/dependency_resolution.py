import inspect
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from typing import Callable, ContextManager, Generator, Type, TypeVar, cast

from openutm_verification.core.execution.config_models import RunContext

T = TypeVar("T")

DEPENDENCIES: dict[object, Callable[..., ContextManager[object]]] = {}
CONTEXT: ContextVar[RunContext] = ContextVar(
    "context",
    default=cast(
        RunContext,
        {
            "scenario_id": "",
            "docs": None,
            "suite_scenario": None,
            "suite_name": None,
        },
    ),
)


def dependency(type: object) -> Callable:
    def wrapper(func: Callable[..., Generator]) -> Callable[..., Generator]:
        DEPENDENCIES[type] = contextmanager(func)
        return func

    return wrapper


def call_with_dependencies(func: Callable[..., T]) -> T:
    """Call a function with its dependencies automatically provided.

    Args:
        func: The function to call.
    Returns:
        The result of the function call.
    """
    sig = inspect.signature(func)
    with provide(*(p.annotation for p in sig.parameters.values())) as dependencies:
        return func(*dependencies)


class DependencyResolver:
    """Resolves dependencies using a provided ExitStack."""

    def __init__(self, stack: ExitStack):
        self.stack = stack
        self._cache: dict[object, object] = {}

    def resolve(self, type_: object) -> object:
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
                dep_instance = self.resolve(param.annotation)
                dep_args.append(dep_instance)

        instance = self.stack.enter_context(dependency_func(*dep_args))
        self._cache[type_] = instance
        return instance


@contextmanager
def provide(*types: object) -> Generator[tuple[object, ...], None, None]:
    """Context manager to provide dependencies for the given types.

    This function recursively resolves dependencies, meaning if a dependency
    function requires other dependencies as parameters, they will be automatically
    provided.

    Args:
        *types: The types of dependencies to provide.
    Yields:
        All the requested dependencies as a tuple.
    """
    with ExitStack() as stack:
        resolver = DependencyResolver(stack)
        instances = [resolver.resolve(t) for t in types]
        yield tuple(instances)
