from contextvars import ContextVar

# Task-local: concurrent speech/evaluator calls cannot inherit another task's job.
work_item_id: ContextVar[str | None] = ContextVar('work_item_id', default=None)
