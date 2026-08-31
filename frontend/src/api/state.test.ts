import { describe, expect, it } from 'vitest'

import {
  errorState,
  idleState,
  isErrorState,
  isIdleState,
  isLoadingState,
  isRefreshingState,
  isSuccessState,
  loadingState,
  refreshingState,
  RequestSequence,
  successState,
  type AsyncState,
} from './state'

describe('AsyncState', () => {
  it('represents each request state and narrows with type guards', () => {
    const idle: AsyncState<string> = idleState()
    const loading = loadingState<string>()
    const refreshing = refreshingState('90.00')
    const success = successState('100.00')
    const failure = errorState<string>(new Error('request failed'))

    expect(isIdleState(idle)).toBe(true)
    expect(isLoadingState(loading)).toBe(true)
    expect(isRefreshingState(refreshing) && refreshing.data).toBe('90.00')
    expect(isSuccessState(success) && success.data).toBe('100.00')
    expect(isErrorState(failure) && failure.error.message).toBe('request failed')
  })
})

describe('RequestSequence', () => {
  it('invalidates an older token when a newer request starts', () => {
    const sequence = new RequestSequence()
    const first = sequence.next()
    const second = sequence.next()

    expect(sequence.isCurrent(first)).toBe(false)
    expect(sequence.isCurrent(second)).toBe(true)
    expect(sequence.isCurrent(second + 1)).toBe(false)
  })
})
