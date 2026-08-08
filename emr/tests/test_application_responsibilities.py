"""Guard focused EMR application responsibilities and minimal inbound dependencies.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

import inspect

from mystack.emr.adapters.inbound.aws import EmrAwsAdapter
from mystack.emr.application.cluster import ClusterCommandHandler
from mystack.emr.application.queries import EmrQueryHandler
from mystack.emr.application.step import StepCommandHandler


def test_handlers_expose_only_their_command_or_query_family() -> None:
    assert _public_coroutines(ClusterCommandHandler) == {
        "add_tags",
        "create_cluster",
        "remove_tags",
        "set_termination_protection",
        "set_visible_to_all_users",
        "terminate_clusters",
    }
    assert _public_coroutines(StepCommandHandler) == {"add_steps", "cancel_steps"}
    assert _public_coroutines(EmrQueryHandler) == {
        "describe_cluster",
        "describe_step",
        "list_bootstrap_actions",
        "list_clusters",
        "list_steps",
    }


def test_inbound_adapter_declares_minimal_command_and_query_ports() -> None:
    parameters = inspect.signature(EmrAwsAdapter.__init__).parameters

    assert set(parameters) == {"self", "cluster_commands", "step_commands", "queries"}
    assert parameters["cluster_commands"].annotation == "EmrClusterCommands"
    assert parameters["step_commands"].annotation == "EmrStepCommands"
    assert parameters["queries"].annotation == "EmrQueries"


def _public_coroutines(value: type[object]) -> set[str]:
    return {
        name
        for name, member in inspect.getmembers(value, inspect.iscoroutinefunction)
        if not name.startswith("_")
    }
