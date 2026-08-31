/** A currency code returned by, or sent to, the ledger API. */
export type CurrencyCode = string

export interface AccountBalance {
  accountId: number
  name: string
  currency: CurrencyCode
  balance: string
  valuationDate: string | null
}

export interface TotalBalance {
  currency: CurrencyCode
  total: string
  valuationDate: string | null
}

export interface ApiErrorDetail {
  code: string
  message: string
  requestId: string
}

/** The common error envelope returned by the API. */
export interface ApiErrorPayload {
  error: ApiErrorDetail
}
