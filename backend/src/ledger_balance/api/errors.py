class ApiFinancialError(ValueError):
    """A value cannot be safely converted or represented by the API."""


class ValuationRateUnavailableError(ApiFinancialError):
    """A non-USD response has no usable valuation rate."""
