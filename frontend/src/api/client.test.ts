import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  fetchAccountBalance,
  fetchSupportedCurrencies,
  fetchTotalBalance,
} from './client'
import {
  ApiClientError,
  isAbortError,
  NETWORK_ERROR_MESSAGE,
  UNKNOWN_ERROR_MESSAGE,
} from './errors'

function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

describe('API client', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', 'https://ledger.example.test/root/')
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllEnvs()
  })

  it('decodes account balances while preserving money strings', async () => {
    const account = {
      accountId: 100,
      name: 'acct100',
      currency: 'EUR',
      balance: '119.55',
      valuationDate: '2026-06-17',
    }
    fetchMock.mockResolvedValueOnce(mockResponse(200, account))

    await expect(fetchAccountBalance('100', 'EUR')).resolves.toEqual(account)
    expect(fetchMock).toHaveBeenCalledWith(
      'https://ledger.example.test/root/api/accounts/100/balance?currency=EUR',
      expect.objectContaining({
        headers: { Accept: 'application/json' },
        cache: 'no-store',
        signal: undefined,
      }),
    )
  })

  it('decodes totals and encodes account and currency path values', async () => {
    const total = {
      currency: 'EUR USD',
      total: '100.00',
      valuationDate: null,
    }
    const controller = new AbortController()
    fetchMock.mockResolvedValueOnce(mockResponse(200, total))

    await expect(fetchTotalBalance('EUR USD', controller.signal)).resolves.toEqual(total)
    expect(fetchMock).toHaveBeenCalledWith(
      'https://ledger.example.test/root/api/balances/total?currency=EUR%20USD',
      expect.objectContaining({ signal: controller.signal }),
    )

    fetchMock.mockResolvedValueOnce(mockResponse(200, total))
    await fetchAccountBalance('acct/100', 'EUR USD')
    expect(fetchMock).toHaveBeenLastCalledWith(
      'https://ledger.example.test/root/api/accounts/acct%2F100/balance?currency=EUR%20USD',
      expect.anything(),
    )
  })

  it('uses a relative URL when no API base URL is configured', async () => {
    vi.stubEnv('VITE_API_BASE_URL', '')
    fetchMock.mockResolvedValueOnce(mockResponse(200, { currency: 'USD', total: '1.00', valuationDate: null }))

    await fetchTotalBalance('USD')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/balances/total?currency=USD',
      expect.anything(),
    )
  })

  it('loads supported currencies from the API', async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse(200, { currencies: ['USD', 'EUR', 'SGD'] }),
    )

    await expect(fetchSupportedCurrencies()).resolves.toEqual({
      currencies: ['USD', 'EUR', 'SGD'],
    })
    expect(fetchMock).toHaveBeenCalledWith(
      'https://ledger.example.test/root/api/currencies',
      expect.objectContaining({ cache: 'no-store' }),
    )
  })

  it('exposes structured not-found errors and marks them non-retryable', async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse(404, {
        error: {
          code: 'ACCOUNT_NOT_FOUND',
          message: 'Account 999 was not found',
          requestId: 'request-404',
        },
      }),
    )

    await expect(fetchAccountBalance('999', 'USD')).rejects.toMatchObject({
      status: 404,
      code: 'ACCOUNT_NOT_FOUND',
      message: 'Account 999 was not found',
      requestId: 'request-404',
      retryable: false,
    })
  })

  it('marks structured service errors as retryable', async () => {
    fetchMock.mockResolvedValueOnce(
      mockResponse(503, {
        error: {
          code: 'DATABASE_UNAVAILABLE',
          message: 'Database unavailable',
          requestId: 'request-503',
        },
      }),
    )

    await expect(fetchTotalBalance('USD')).rejects.toMatchObject({
      status: 503,
      code: 'DATABASE_UNAVAILABLE',
      requestId: 'request-503',
      retryable: true,
    })
  })

  it('uses a safe fallback for malformed error bodies', async () => {
    fetchMock.mockResolvedValueOnce(mockResponse(500, { secret: 'do not expose this' }))

    const result = fetchTotalBalance('USD')
    await expect(result).rejects.toBeInstanceOf(ApiClientError)
    await expect(result).rejects.toMatchObject({
      status: 500,
      code: 'HTTP_500',
      message: UNKNOWN_ERROR_MESSAGE,
      requestId: null,
      retryable: true,
    })
    await expect(result).rejects.not.toThrow('do not expose this')
  })

  it('normalizes network failures without exposing the underlying error', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('socket details are private'))

    const result = fetchTotalBalance('USD')
    await expect(result).rejects.toMatchObject({
      status: 0,
      code: 'NETWORK_ERROR',
      message: NETWORK_ERROR_MESSAGE,
      requestId: null,
      retryable: true,
    })
    await expect(result).rejects.not.toThrow('socket details are private')
  })

  it('propagates abort errors unchanged', async () => {
    const abortError = new DOMException('The operation was aborted.', 'AbortError')
    fetchMock.mockRejectedValueOnce(abortError)

    await expect(fetchTotalBalance('USD')).rejects.toBe(abortError)
    expect(isAbortError(abortError)).toBe(true)
  })
})
