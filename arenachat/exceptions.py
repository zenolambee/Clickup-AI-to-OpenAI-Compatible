from __future__ import annotations


class ArenaChatError(Exception):
    def __init__(self, message: str, status_code: int = 500) -> None:
        self.status_code = status_code
        super().__init__(message)
