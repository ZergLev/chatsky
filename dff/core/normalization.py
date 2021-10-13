import logging

from typing import Union, Callable, Optional, Any


from .context import Context
from .types import NodeLabel3Type, NodeLabelType, ConditionType

from pydantic import validate_arguments, BaseModel


logger = logging.getLogger(__name__)


Actor = BaseModel


@validate_arguments
def normalize_node_label(node_label: NodeLabelType, default_flow_label: str = "") -> Union[Callable, NodeLabel3Type]:
    if isinstance(node_label, Callable):

        @validate_arguments
        def get_node_label_handler(ctx: Context, actor: Actor, *args, **kwargs) -> NodeLabel3Type:
            try:
                res = node_label(ctx, actor, *args, **kwargs)
                res = (str(res[0]), str(res[1]), float(res[2]))
                node = actor.plot.get_node(res)
                if not node:
                    raise Exception(f"Unknown transitions {res} for {actor.plot}")
            except Exception as exc:
                res = None
                logger.error(f"Exception {exc} of function {node_label}", exc_info=exc)
            return res

        return get_node_label_handler  # create wrap to get uniq key for dictionary
    elif isinstance(node_label, str):
        return (default_flow_label, node_label, float("-inf"))
    elif isinstance(node_label, tuple) and len(node_label) == 2 and isinstance(node_label[-1], float):
        return (default_flow_label, node_label[0], node_label[-1])
    elif isinstance(node_label, tuple) and len(node_label) == 2 and isinstance(node_label[-1], str):
        return (node_label[0], node_label[-1], float("-inf"))
    elif isinstance(node_label, tuple) and len(node_label) == 3:
        return (node_label[0], node_label[1], node_label[2])
    raise NotImplementedError(f"Unexpected node label {node_label}")


@validate_arguments
def normalize_condition(condition: ConditionType) -> Callable:
    if isinstance(condition, Callable):

        @validate_arguments
        def callable_condition_handler(ctx: Context, actor: Actor, *args, **kwargs) -> bool:
            try:
                return condition(ctx, actor, *args, **kwargs)
            except Exception as exc:
                logger.error(f"Exception {exc} of function {condition}", exc_info=exc)
                return False

        return callable_condition_handler
    raise NotImplementedError(f"Unexpected condition {condition}")


@validate_arguments
def normalize_transitions(
    transitions: dict[NodeLabelType, ConditionType]
) -> dict[Union[Callable, NodeLabel3Type], Callable]:
    transitions = {
        normalize_node_label(node_label): normalize_condition(condition)
        for node_label, condition in transitions.items()
    }
    return transitions


@validate_arguments
def normalize_response(response: Any) -> Callable:
    if isinstance(response, Callable):
        return response
    else:

        @validate_arguments
        def response_handler(ctx: Context, actor: Actor, *args, **kwargs):
            return response

        return response_handler


@validate_arguments
def normalize_processing(processing: Optional[dict[Any, Callable]]) -> Callable:
    if isinstance(processing, dict):

        @validate_arguments
        def processing_handler(ctx: Context, actor: Actor, *args, **kwargs) -> Context:
            for processing_name, processing_func in processing.items():
                try:
                    ctx = processing_func(ctx, actor, *args, **kwargs)
                except Exception as exc:
                    logger.error(f"Exception {exc} for {processing_name=} and {processing_func=}", exc_info=exc)
            return ctx

        return processing_handler
    raise NotImplementedError(f"Unexpected processing {processing}")
