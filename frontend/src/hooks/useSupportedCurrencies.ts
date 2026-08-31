import { useEffect, useState } from 'react'

import { fetchSupportedCurrencies } from '../api/client'
import { isAbortError, normalizeApiError } from '../api/errors'
import { errorState, loadingState, successState, type AsyncState } from '../api/state'
import type { SupportedCurrencies } from '../api/types'

export function useSupportedCurrencies(): AsyncState<SupportedCurrencies> {
  const [state, setState] = useState<AsyncState<SupportedCurrencies>>(loadingState())

  useEffect(() => {
    const controller = new AbortController()

    void fetchSupportedCurrencies(controller.signal)
      .then((currencies) => setState(successState(currencies)))
      .catch((error: unknown) => {
        if (!isAbortError(error)) {
          setState(errorState(error instanceof Error ? error : normalizeApiError(error)))
        }
      })

    return () => controller.abort()
  }, [])

  return state
}
