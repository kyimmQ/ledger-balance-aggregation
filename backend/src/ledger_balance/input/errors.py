from pathlib import Path


class InputFileError(ValueError):
    def __init__(self, path: Path, row: int, field: str, message: str) -> None:
        self.path = path
        self.row = row
        self.field = field
        self.message = message
        super().__init__(f"{path}:{row}: field '{field}': {message}")
