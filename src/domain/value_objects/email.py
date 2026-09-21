from __future__ import annotations

import re
from dataclasses import dataclass

from src.domain.errors.domain_errors import InvalidEmailError

_EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


@dataclass(frozen=True, slots=True)
class Email:
    value: str

    def __post_init__(self) -> None:
        normalized = self.value.strip().lower()
        if not _EMAIL_REGEX.match(normalized):
            raise InvalidEmailError(self.value)
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value
