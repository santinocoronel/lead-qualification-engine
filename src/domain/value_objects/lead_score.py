from __future__ import annotations

from dataclasses import dataclass

from src.domain.errors.domain_errors import InvalidLeadScoreError


@dataclass(frozen=True, slots=True)
class LeadScore:
    value: int

    def __post_init__(self) -> None:
        if not (0 <= self.value <= 100):
            raise InvalidLeadScoreError(self.value)

    def __int__(self) -> int:
        return self.value
