export const NETWORK_ERROR_MESSAGE =
  'Unable to reach the ledger service. Please try again.'
export const UNKNOWN_ERROR_MESSAGE =
  'The ledger service returned an unexpected response. Please try again.'

export interface ApiClientErrorOptions {
  status: number
  code: string
  message: string
  requestId?: string | null
  retryable?: boolean
}

export class ApiClientError extends Error {
  readonly status: number
  readonly code: string
  readonly requestId: string | null
  readonly retryable: boolean

  constructor({
    status,
    code,
    message,
    requestId = null,
    retryable = isRetryableStatus(status),
  }: ApiClientErrorOptions) {
    super(message)
    this.name = 'ApiClientError'
    this.status = status
    this.code = code
    this.requestId = requestId
    this.retryable = retryable
  }
}

/** Return true for browser and cross-realm abort errors. */
export function isAbortError(error: unknown): boolean {
  if (typeof DOMException !== 'undefined' && error instanceof DOMException) {
    return error.name === 'AbortError'
  }

  return isRecord(error) && error.name === 'AbortError'
}

/** Convert a failed request or response into a safe, user-facing API error. */
export function normalizeApiError(
  error: unknown,
  status = 0,
): ApiClientError {
  if (error instanceof ApiClientError) {
    return error
  }

  const detail = getApiErrorDetail(error)
  if (detail) {
    return new ApiClientError({
      status,
      code: detail.code,
      message: detail.message,
      requestId: detail.requestId,
      retryable: isRetryableStatus(status),
    })
  }

  if (status === 0) {
    return new ApiClientError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: NETWORK_ERROR_MESSAGE,
      retryable: true,
    })
  }

  return new ApiClientError({
    status,
    code: `HTTP_${status}`,
    message: UNKNOWN_ERROR_MESSAGE,
    retryable: isRetryableStatus(status),
  })
}

function getApiErrorDetail(
  value: unknown,
): { code: string; message: string; requestId: string } | null {
  if (!isRecord(value) || !isRecord(value.error)) {
    return null
  }

  const { code, message, requestId } = value.error
  if (
    typeof code !== 'string' ||
    typeof message !== 'string' ||
    typeof requestId !== 'string'
  ) {
    return null
  }

  return { code, message, requestId }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isRetryableStatus(status: number): boolean {
  return status === 0 || status === 408 || status === 425 || status === 429 || status >= 500
}
