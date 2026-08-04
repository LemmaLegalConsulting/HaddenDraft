"""Bounded execution, validation, and repair for read-only AI tool plans."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolEvaluation:
    success: bool
    code: str
    message: str = ""


@dataclass(frozen=True)
class ToolLoopResult:
    result: object
    evaluation: ToolEvaluation
    attempts: tuple

    @property
    def success(self):
        return self.evaluation.success

    def trace(self):
        return [
            {
                "attempt": attempt["attempt"],
                "plan": attempt["plan"],
                "success": attempt["evaluation"].success,
                "code": attempt["evaluation"].code,
                "message": attempt["evaluation"].message,
            }
            for attempt in self.attempts
        ]


def run_tool_with_repair(
    initial_plan,
    *,
    execute,
    evaluate,
    repair,
    max_attempts=2,
):
    """Run a plan, validate its postconditions, and apply bounded repairs."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    plan = initial_plan
    attempts = []
    result = None
    evaluation = ToolEvaluation(False, "not_run", "The tool plan was not executed.")

    for attempt_number in range(1, max_attempts + 1):
        result = execute(plan)
        evaluation = evaluate(plan, result)
        attempts.append(
            {
                "attempt": attempt_number,
                "plan": dict(plan) if isinstance(plan, dict) else plan,
                "evaluation": evaluation,
            }
        )
        if evaluation.success:
            break
        next_plan = repair(plan, result, evaluation)
        if next_plan is None or next_plan == plan:
            break
        plan = next_plan

    return ToolLoopResult(result=result, evaluation=evaluation, attempts=tuple(attempts))
