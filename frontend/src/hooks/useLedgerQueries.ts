import { useCallback, useEffect, useRef, useState } from 'react'

import {
  fetchAccountBalance,
  fetchTotalBalance,
} from '../api/client'
import {
  ApiClientError,
  isAbortError,
  normalizeApiError,
} from '../api/errors'
import {
  errorState,
  idleState,
  loadingState,
  RequestSequence,
  successState,
  type AsyncState,
} from '../api/state'
import type { AccountBalance, CurrencyCode, TotalBalance } from '../api/types'

export type LedgerQueryErrorCode =
  | 'ACCOUNT_NOT_FOUND'
  | 'DATASET_NOT_READY'
  | 'VALUATION_RATE_UNAVAILABLE'
  | 'NETWORK_ERROR'
  | 'RATE_LIMITED'
  | 'DATABASE_UNAVAILABLE'
  | 'DATABASE_TIMEOUT'
  | 'UNSUPPORTED_CURRENCY'
  | 'INVALID_CURRENCY'
  | 'UNKNOWN'

export interface LedgerQueryErrorDetails {
  code: LedgerQueryErrorCode
  message: string
}

class LedgerQueryFailure extends Error {
  readonly code: LedgerQueryErrorCode

  constructor(code: LedgerQueryErrorCode, message: string, cause?: unknown) {
    super(message, { cause })
    this.name = 'LedgerQueryFailure'
    this.code = code
  }
}

export interface UseLedgerQueriesResult {
  currency: CurrencyCode
  totalState: AsyncState<TotalBalance>
  accountState: AsyncState<AccountBalance>
  lookupAccount: (accountId: string) => void
  changeCurrency: (currency: CurrencyCode) => void
}

const initialCurrency: CurrencyCode = 'USD'

/**
 * Owns the dashboard's request lifecycle. Each resource has its own
 * controller and sequence so an account refresh cannot invalidate a total,
 * and vice versa.
 */
export function useLedgerQueries(): UseLedgerQueriesResult {
  const [currency, setCurrency] = useState<CurrencyCode>(initialCurrency)
  const [totalState, setTotalState] = useState<AsyncState<TotalBalance>>(idleState())
  const [accountState, setAccountState] = useState<AsyncState<AccountBalance>>(idleState())
  const totalController = useRef<AbortController | null>(null)
  const accountController = useRef<AbortController | null>(null)
  const totalSequence = useRef(new RequestSequence())
  const accountSequence = useRef(new RequestSequence())
  const lastAccountId = useRef<string | null>(null)
  const activeAccountRequest = useRef<{ accountId: string; currency: CurrencyCode } | null>(null)
  const accountLoading = useRef(false)

  const loadTotal = useCallback((requestedCurrency: CurrencyCode) => {
    totalController.current?.abort()
    const controller = new AbortController()
    totalController.current = controller
    const token = totalSequence.current.next()
    setTotalState(loadingState())

    void fetchTotalBalance(requestedCurrency, controller.signal)
      .then((data) => {
        if (totalSequence.current.isCurrent(token)) {
          setTotalState(successState(data))
        }
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || !totalSequence.current.isCurrent(token)) {
          return
        }
        setTotalState(errorState(toLedgerError(error)))
      })
  }, [])

  const loadAccount = useCallback(
    (accountId: string, requestedCurrency: CurrencyCode, force = false) => {
      if (
        !force &&
        accountLoading.current &&
        activeAccountRequest.current?.accountId === accountId &&
        activeAccountRequest.current.currency === requestedCurrency
      ) {
        return
      }

      accountController.current?.abort()
      const controller = new AbortController()
      accountController.current = controller
      activeAccountRequest.current = { accountId, currency: requestedCurrency }
      accountLoading.current = true
      const token = accountSequence.current.next()
      setAccountState(loadingState())

      void fetchAccountBalance(accountId, requestedCurrency, controller.signal)
        .then((data) => {
          if (accountSequence.current.isCurrent(token)) {
            accountLoading.current = false
            setAccountState(successState(data))
          }
        })
        .catch((error: unknown) => {
          if (isAbortError(error) || !accountSequence.current.isCurrent(token)) {
            return
          }
          accountLoading.current = false
          setAccountState(errorState(toLedgerError(error)))
        })
    },
    [],
  )

  const lookupAccount = useCallback(
    (accountId: string) => {
      lastAccountId.current = accountId
      loadAccount(accountId, currency)
    },
    [currency, loadAccount],
  )

  const changeCurrency = useCallback(
    (nextCurrency: CurrencyCode) => {
      setCurrency(nextCurrency)
      loadTotal(nextCurrency)
      if (lastAccountId.current !== null) {
        loadAccount(lastAccountId.current, nextCurrency, true)
      }
    },
    [loadAccount, loadTotal],
  )

  useEffect(() => {
    let active = true
    const totalSequenceForCleanup = totalSequence.current
    const accountSequenceForCleanup = accountSequence.current
    queueMicrotask(() => {
      if (active) {
        loadTotal(initialCurrency)
      }
    })

    return () => {
      active = false
      totalController.current?.abort()
      accountController.current?.abort()
      totalSequenceForCleanup.next()
      accountSequenceForCleanup.next()
    }
  }, [loadTotal])

  return {
    currency,
    totalState,
    accountState,
    lookupAccount,
    changeCurrency,
  }
}

export function getLedgerQueryError(error: Error): LedgerQueryErrorDetails {
  if (error instanceof LedgerQueryFailure) {
    return { code: error.code, message: error.message }
  }

  if (error instanceof ApiClientError) {
    return {
      code: getKnownErrorCode(error.code),
      message: getSafeMessage(error.code),
    }
  }

  return { code: 'UNKNOWN', message: 'The ledger service returned an unexpected response.' }
}

function toLedgerError(error: unknown): Error {
  if (error instanceof ApiClientError) {
    const code = getKnownErrorCode(error.code)
    return new LedgerQueryFailure(code, getSafeMessage(code), error)
  }

  const normalized = normalizeApiError(error)
  const code = getKnownErrorCode(normalized.code)
  return new LedgerQueryFailure(code, getSafeMessage(code), normalized)
}

function getSafeMessage(code: string): string {
  switch (code) {
    case 'ACCOUNT_NOT_FOUND':
      return 'That account was not found in the current ledger.'
    case 'DATASET_NOT_READY':
      return 'The ledger dataset is not available right now. Please try again later.'
    case 'VALUATION_RATE_UNAVAILABLE':
      return 'A valuation rate is unavailable for this currency. Please choose another currency.'
    case 'NETWORK_ERROR':
      return 'Unable to reach the ledger service. Please try again.'
    case 'RATE_LIMITED':
      return 'The ledger service is busy. Please try again shortly.'
    case 'DATABASE_UNAVAILABLE':
    case 'DATABASE_TIMEOUT':
      return 'The ledger service is temporarily unavailable. Please try again.'
    case 'UNSUPPORTED_CURRENCY':
      return 'That currency is not currently supported by the ledger.'
    case 'INVALID_CURRENCY':
      return 'Choose a valid display currency.'
    default:
      return 'The ledger service returned an unexpected response. Please try again.'
  }
}

function getKnownErrorCode(code: string): LedgerQueryErrorCode {
  switch (code) {
    case 'ACCOUNT_NOT_FOUND':
    case 'DATASET_NOT_READY':
    case 'VALUATION_RATE_UNAVAILABLE':
    case 'NETWORK_ERROR':
    case 'RATE_LIMITED':
    case 'DATABASE_UNAVAILABLE':
    case 'DATABASE_TIMEOUT':
    case 'UNSUPPORTED_CURRENCY':
    case 'INVALID_CURRENCY':
      return code
    default:
      return 'UNKNOWN'
  }
}
