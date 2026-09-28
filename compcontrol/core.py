"""Compatibility entry point for clients. handle() only plans; it never executes."""
from dataclasses import dataclass
from .planner import plan_request


@dataclass(frozen=True)
class Result:
    message: str
    action: str = 'none'
    confirmation_required: bool = False


class Assistant:
    def handle(self, text):
        plan = plan_request(text)
        return Result(plan.message, plan.actions[0].kind if plan.actions else 'none', bool(plan.actions))
