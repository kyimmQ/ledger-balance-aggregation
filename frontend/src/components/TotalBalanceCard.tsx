import type { CurrencyCode } from './CurrencySelector'

export type BalanceDisplayState =
  | 'idle'
  | 'loading'
  | 'refreshing'
  | 'success'
  | 'not-found'
  | 'empty'
  | 'error'

export interface TotalBalanceCardProps {
  currency: CurrencyCode
  total?: string
  valuationDate?: string | null
  state: BalanceDisplayState
  message?: string
  pending?: boolean
  onRetry?: () => void
}

function TotalBalanceCard({
  currency,
  total,
  valuationDate,
  state,
  message,
  pending = state === 'loading' || state === 'refreshing',
  onRetry,
}: TotalBalanceCardProps) {
  const hasValue = state === 'success' || state === 'refreshing'
  const valueTone = total === undefined ? 'normal' : getMoneyTone(total)

  return (
    <section
      className={`card total-card state-${state}`}
      aria-labelledby="total-balance-heading"
      aria-busy={pending}
    >
      <div className="card-heading-row">
        <div>
          <p className="card-kicker">Portfolio view</p>
          <h2 id="total-balance-heading">Total balance</h2>
        </div>
        <span className="currency-chip">{currency}</span>
      </div>
      {state === 'idle' && (
        <p className="empty-message">
          Your combined balance will appear here after a ledger request.
        </p>
      )}
      {state === 'loading' && (
        <p className="loading-message" role="status" aria-live="polite">
          Loading total balance…
        </p>
      )}
      {state === 'refreshing' && (
        <p className="loading-message refreshing-message" role="status" aria-live="polite">
          Refreshing total balance…
        </p>
      )}
      {hasValue && total !== undefined && (
        <div className="balance-result">
          <p className={`money-value money-${valueTone}`}>
            <span>{total}</span>
          </p>
          {valueTone !== 'normal' && (
            <p className={`balance-context balance-context-${valueTone}`}>
              {valueTone === 'zero' ? 'Zero balance' : 'Negative balance'}
            </p>
          )}
          {(valuationDate || currency === 'USD') && (
            <p className="valuation-date">
              {valuationDate ? `Valued ${valuationDate}` : 'Stored USD'}
            </p>
          )}
          {(state === 'success' || state === 'refreshing') && onRetry && (
            <button type="button" className="refresh-button" onClick={onRetry} disabled={pending}>
              {state === 'refreshing' ? 'Refreshing total balance…' : 'Refresh total balance'}
            </button>
          )}
        </div>
      )}
      {(state === 'not-found' || state === 'empty' || state === 'error') && (
        <div className="error-content" role="group" aria-label="Total balance request result">
          <p className="empty-message">{message ?? getDefaultMessage(state)}</p>
          {(state === 'empty' || state === 'error') && onRetry && (
            <button type="button" className="retry-button" onClick={onRetry}>
              Retry total balance
            </button>
          )}
        </div>
      )}
    </section>
  )
}

function getDefaultMessage(state: Exclude<BalanceDisplayState, 'idle' | 'loading' | 'success'>): string {
  if (state === 'empty') {
    return 'The ledger dataset is not available right now.'
  }
  return 'The total balance is not available yet.'
}

function getMoneyTone(value: string): 'normal' | 'negative' | 'zero' {
  const trimmed = value.trim()
  if (/^-/.test(trimmed) && !/^-0+(?:\.0+)?$/.test(trimmed)) {
    return 'negative'
  }
  if (/^[+-]?0+(?:\.0+)?$/.test(trimmed)) {
    return 'zero'
  }
  return 'normal'
}

export default TotalBalanceCard
