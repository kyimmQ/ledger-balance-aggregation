import { isAbortError, normalizeApiError } from './errors'
import type { AccountBalance, TotalBalance } from './types'

const API_PATH_PREFIX = '/api'

export async function fetchAccountBalance(
  accountId: string,
  currency: string,
  signal?: AbortSignal,
): Promise<AccountBalance> {
  const path = `${API_PATH_PREFIX}/accounts/${encodeURIComponent(accountId)}/balance?currency=${encodeURIComponent(currency)}`
  return requestJson<AccountBalance>(path, signal)
}

export async function fetchTotalBalance(
  currency: string,
  signal?: AbortSignal,
): Promise<TotalBalance> {
  const path = `${API_PATH_PREFIX}/balances/total?currency=${encodeURIComponent(currency)}`
  return requestJson<TotalBalance>(path, signal)
}

export function buildApiUrl(path: string): string {
  const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim() ?? ''
  const baseUrl = configuredBaseUrl.replace(/\/+$/, '')
  return `${baseUrl}${path}`
}

async function requestJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let response: Response
  try {
    response = await fetch(buildApiUrl(path), {
      headers: { Accept: 'application/json' },
      cache: 'no-store',
      signal,
    })
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }
    throw normalizeApiError(error)
  }

  const payload = await parseJsonSafely(response)
  if (!response.ok) {
    throw normalizeApiError(payload, response.status)
  }

  if (payload === undefined) {
    throw normalizeApiError(undefined, response.status)
  }

  return payload as T
}

async function parseJsonSafely(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch (error) {
    if (isAbortError(error)) {
      throw error
    }
    return undefined
  }
}
