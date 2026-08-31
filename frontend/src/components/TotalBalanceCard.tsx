import type { CurrencyCode } from './CurrencySelector'

export type BalanceDisplayState =
  | 'idle'
  | 'loading'
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
}

function TotalBalanceCard({
  currency,
  total,
  valuationDate,
  state,
  message,
}: TotalBalanceCardProps) {
  return (
    <section className={`card total-card state-${state}`} aria-labelledby="total-balance-heading">
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
      {state === 'success' && total !== undefined && (
        <div className="balance-result">
          <p className="money-value">{total}</p>
          {(valuationDate || currency === 'USD') && (
            <p className="valuation-date">
              {valuationDate ? `Valued ${valuationDate}` : 'Stored USD'}
            </p>
          )}
        </div>
      )}
      {(state === 'not-found' || state === 'empty' || state === 'error') && (
        <p className="empty-message">{message ?? getDefaultMessage(state)}</p>
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

export default TotalBalanceCard
