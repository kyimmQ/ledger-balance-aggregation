export type BalanceDisplayState =
  | 'idle'
  | 'loading'
  | 'refreshing'
  | 'success'
  | 'not-found'
  | 'empty'
  | 'error'

export function getMoneyTone(value: string): 'normal' | 'negative' | 'zero' {
  const trimmed = value.trim()
  if (/^-/.test(trimmed) && !/^-0+(?:\.0+)?$/.test(trimmed)) {
    return 'negative'
  }
  if (/^[+-]?0+(?:\.0+)?$/.test(trimmed)) {
    return 'zero'
  }
  return 'normal'
}
