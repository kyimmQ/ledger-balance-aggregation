export type AsyncState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'error'; error: Error }

export const idleState = (): AsyncState<never> => ({ status: 'idle' })

export const loadingState = <T = never>(): AsyncState<T> => ({ status: 'loading' })

export const successState = <T>(data: T): AsyncState<T> => ({
  status: 'success',
  data,
})

export const errorState = <T = never>(error: Error): AsyncState<T> => ({
  status: 'error',
  error,
})

export function isIdleState<T>(state: AsyncState<T>): state is { status: 'idle' } {
  return state.status === 'idle'
}

export function isLoadingState<T>(state: AsyncState<T>): state is { status: 'loading' } {
  return state.status === 'loading'
}

export function isSuccessState<T>(
  state: AsyncState<T>,
): state is { status: 'success'; data: T } {
  return state.status === 'success'
}

export function isErrorState<T>(
  state: AsyncState<T>,
): state is { status: 'error'; error: Error } {
  return state.status === 'error'
}

/** Monotonically increasing tokens for ignoring superseded request results. */
export class RequestSequence {
  private currentToken = 0

  next(): number {
    this.currentToken += 1
    return this.currentToken
  }

  isCurrent(token: number): boolean {
    return token === this.currentToken
  }
}
