import inspect
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from typing import Callable, Generator, Type, TypeVar

from openutm_verification.core.execution.config_models import RunContext

T = TypeVar('T')

DEPENDENCIES: ContextVar[dict[Type, Callable[..., object]]] = ContextVar("dependencies", default={})
CONTEXT: ContextVar = ContextVar[RunContext]("context", default={"scenario_id": ""})


def get_context() -> RunContext:
    """Get the current run context.

    Returns:
        The current RunContext.
    """
    return CONTEXT.get()


def dependency(type: Type) -> Callable:
    def wrapper(func: Callable[..., object]) -> Callable[..., object]:
        deps = DEPENDENCIES.get()
        deps[type] = contextmanager(func)
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


@contextmanager
def provide(*types: Type[T]) -> Generator[tuple[T, ...], None, None]:
    """Context manager to provide dependencies for the given types.

    This function recursively resolves dependencies, meaning if a dependency
    function requires other dependencies as parameters, they will be automatically
    provided.

    Args:
        *types: The types of dependencies to provide.
    Yields:
        All the requested dependencies as a tuple.
    """
    _cache: dict[Type, object] = {}

    def _resolve_dependency(type_: Type, stack: ExitStack) -> object:
        if type_ in _cache:
            return _cache[type_]

        deps = DEPENDENCIES.get()
        if type_ not in deps:
            raise ValueError(f"No dependency registered for type {type_}")

        dependency_func = deps[type_]
        sig = inspect.signature(dependency_func)

        # Resolve dependencies of this dependency
        dep_args = []
        for param in sig.parameters.values():
            if param.annotation is not inspect.Parameter.empty and param.annotation is not type(None):
                dep_instance = _resolve_dependency(param.annotation, stack)
                dep_args.append(dep_instance)

        instance = stack.enter_context(dependency_func(*dep_args))
        _cache[type_] = instance
        return instance

    with ExitStack() as stack:
        instances = {type_: _resolve_dependency(type_, stack) for type_ in types}
        yield tuple(instances[type_] for type_ in types)
