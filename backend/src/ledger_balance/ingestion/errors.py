"""Exceptions raised by ingestion processing."""


class WorkItemPersistenceError(RuntimeError):
    """A transaction work item could not be persisted."""

    def __init__(self, sequence: int, cause: Exception) -> None:
        self.sequence = sequence
        super().__init__(f"transaction {sequence} persistence failed: {cause}")
