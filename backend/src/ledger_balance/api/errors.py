class ApiFinancialError(ValueError):
    """A value cannot be safely converted or represented by the API."""


class ValuationRateUnavailableError(ApiFinancialError):
    """A non-USD response has no usable valuation rate."""


class ApiRouteError(Exception):
    """A known failure with a stable public HTTP representation."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.status_code = status_code
        self.code = code
        self.public_message = message
        super().__init__(message)


class InvalidAccountIdError(ApiRouteError):
    def __init__(self, raw: str) -> None:
        super().__init__(400, "INVALID_ACCOUNT_ID", f"Invalid account ID: {raw!r}")


class InvalidCurrencyError(ApiRouteError):
    def __init__(self) -> None:
        super().__init__(400, "INVALID_CURRENCY", "Currency must be 3–8 ASCII letters")  # noqa: RUF001


class UnsupportedCurrencyError(ApiRouteError):
    def __init__(self, currency: str) -> None:
        super().__init__(400, "UNSUPPORTED_CURRENCY", f"Currency {currency} is not supported")


class DatasetNotReadyError(ApiRouteError):
    def __init__(self) -> None:
        super().__init__(503, "DATASET_NOT_READY", "No balance dataset is currently available")


class AccountNotFoundError(ApiRouteError):
    def __init__(self, account_id: int) -> None:
        super().__init__(404, "ACCOUNT_NOT_FOUND", f"Account {account_id} was not found")


class ValuationRateUnavailableApiError(ApiRouteError):
    def __init__(self, currency: str) -> None:
        super().__init__(
            503,
            "VALUATION_RATE_UNAVAILABLE",
            f"No valuation rate is available for {currency}",
        )


class DatabaseUnavailableError(ApiRouteError):
    def __init__(self) -> None:
        super().__init__(503, "DATABASE_UNAVAILABLE", "Database unavailable")


class DatabaseTimeoutError(ApiRouteError):
    def __init__(self) -> None:
        super().__init__(504, "DATABASE_TIMEOUT", "Database query timed out")
