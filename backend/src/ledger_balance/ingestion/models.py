"""Public contracts returned by the ingestion service."""

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class IngestionResult:
    transaction_count: int
    account_count: int
    rate_count: int
    total_usd: Decimal
