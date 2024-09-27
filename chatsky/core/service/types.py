"""
Types
-----
This module defines type aliases used throughout the ``Core.Service`` module.

The classes and special types in this module can include data models,
data structures, and other types that are defined for type hinting.
"""

from __future__ import annotations
from enum import unique, Enum
from typing import Callable, Union, Awaitable, Dict, Optional, Iterable, Any, Protocol, Hashable, TYPE_CHECKING
from typing_extensions import TypeAlias
from pydantic import BaseModel


if TYPE_CHECKING:
    from chatsky.core import Context, Message, Pipeline


class PipelineRunnerFunction(Protocol):
    """
    Protocol for pipeline running.
    """

    def __call__(
        self, message: Message, ctx_id: Optional[Hashable] = None, update_ctx_misc: Optional[dict] = None
    ) -> Awaitable[Context]:
        """
        :param message: User request for pipeline to process.
        :param ctx_id:
            ID of the context that the new request belongs to.
            Optional, None by default.
            If set to `None`, a new context will be created with `message` being the first request.
        :param update_ctx_misc:
            Dictionary to be passed as an argument to `ctx.misc.update`.
            This argument can be used to store values in the `misc` dictionary before anything else runs.
            Optional; None by default.
            If set to `None`, `ctx.misc.update` will not be called.
        :return:
            Context instance that pipeline processed.
            The context instance has the id of `ctx_id`.
            If `ctx_id` is `None`, context instance has an id generated with `uuid.uuid4`.
        """


@unique
class ComponentExecutionState(str, Enum):
    """
    Enum, representing pipeline component execution state.
    These states are stored in :py:attr:`~chatsky.core.context.FrameworkData.service_states`,
    that should always be requested with `NOT_RUN` being default fallback.
    Following states are supported:

    - NOT_RUN: component has not been executed yet (the default one),
    - RUNNING: component is currently being executed,
    - FINISHED: component executed successfully,
    - FAILED: component execution failed.
    """

    NOT_RUN = "NOT_RUN"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"


@unique
class GlobalExtraHandlerType(str, Enum):
    """
    Enum, representing types of global extra handlers, that can be set applied for a pipeline.
    The following types are supported:

    - BEFORE_ALL: function called before each pipeline call,
    - BEFORE: function called before each component,
    - AFTER: function called after each component,
    - AFTER_ALL: function called after each pipeline call.
    """

    BEFORE_ALL = "BEFORE_ALL"
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    AFTER_ALL = "AFTER_ALL"


@unique
class ExtraHandlerType(str, Enum):
    """
    Enum, representing wrapper execution stage: before or after the wrapped function.
    The following types are supported:

    - UNDEFINED: extra handler function with undetermined execution stage,
    - BEFORE: extra handler function called before component,
    - AFTER: extra handler function called after component.
    """

    UNDEFINED = "UNDEFINED"
    BEFORE = "BEFORE"
    AFTER = "AFTER"


StartConditionCheckerFunction: TypeAlias = Callable[["Context", "Pipeline"], bool]
"""
A function type for components `start_conditions`.
Accepts context and pipeline, returns boolean (whether service can be launched).
"""


StartConditionCheckerAggregationFunction: TypeAlias = Callable[[Iterable[bool]], bool]
"""
A function type for creating aggregation `start_conditions` for components.
Accepts list of functions (other start_conditions to aggregate), returns boolean (whether service can be launched).
"""


ExtraHandlerConditionFunction: TypeAlias = Callable[[str], bool]
"""
A function type used during global extra handler initialization to determine
whether extra handler should be applied to component with given path or not.
Checks components path to be in whitelist (if defined) and not to be in blacklist (if defined).
Accepts str (component path), returns boolean (whether extra handler should be applied).
"""


class ServiceRuntimeInfo(BaseModel):
    """
    Type of object, that is passed to components in runtime.
    Contains current component info (`name`, `path`, `timeout`, `asynchronous`).
    Also contains `execution_state` - a dictionary,
    containing execution states of other components mapped to their paths.
    """

    name: str
    path: str
    timeout: Optional[float]
    asynchronous: bool
    execution_state: Dict[str, ComponentExecutionState]


ExtraHandlerFunction: TypeAlias = Union[
    Callable[["Context"], Any],
    Callable[["Context", "Pipeline"], Any],
    Callable[["Context", "Pipeline", "ExtraHandlerRuntimeInfo"], Any],
]
"""
A function type for creating extra handler (before and after functions).
Can accept current dialog context, pipeline, and current extra handler info.
"""


class ExtraHandlerRuntimeInfo(BaseModel):
    func: ExtraHandlerFunction
    stage: ExtraHandlerType
    component: ServiceRuntimeInfo


"""
Type of object, that is passed to wrappers in runtime.
Contains current wrapper info (`name`, `stage`).
Also contains `component` - runtime info of the component this wrapper is attached to.
"""


ServiceFunction: TypeAlias = Union[
    Callable[["Context"], None],
    Callable[["Context"], Awaitable[None]],
    Callable[["Context", "Pipeline"], None],
    Callable[["Context", "Pipeline"], Awaitable[None]],
    Callable[["Context", "Pipeline", ServiceRuntimeInfo], None],
    Callable[["Context", "Pipeline", ServiceRuntimeInfo], Awaitable[None]],
]
"""
A function type for creating service handlers.
Can accept current dialog context, pipeline, and current service info.
Can be both synchronous and asynchronous.
"""