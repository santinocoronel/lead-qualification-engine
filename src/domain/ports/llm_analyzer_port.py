from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.domain.value_objects.enums import UrgencyLevel


@dataclass(frozen=True, slots=True)
class LLMAnalysisResult:
    score: int
    urgency: UrgencyLevel
    budget_estimate: str
    summary: str


class LLMAnalyzerPort(ABC):
    @abstractmethod
    async def analyze_lead(
        self,
        company_name: str,
        inquiry_text: str,
        source: str,
    ) -> LLMAnalysisResult: ...
