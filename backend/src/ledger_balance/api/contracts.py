from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class AccountBalanceResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    account_id: int = Field(alias="accountId")
    name: str
    currency: str
    balance: str
    valuation_date: date | None = Field(alias="valuationDate")


class TotalBalanceResponse(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    currency: str
    total: str
    valuation_date: date | None = Field(alias="valuationDate")


class ErrorDetail(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True)

    code: str
    message: str
    request_id: str = Field(alias="requestId")


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True)

    error: ErrorDetail
