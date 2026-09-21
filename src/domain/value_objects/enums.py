from enum import StrEnum


class UrgencyLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class QualificationStatus(StrEnum):
    QUALIFIED = "QUALIFIED"
    DISQUALIFIED = "DISQUALIFIED"
    REVIEW_NEEDED = "REVIEW_NEEDED"
