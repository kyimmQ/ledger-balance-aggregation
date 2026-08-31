import type { CurrencyCode } from './CurrencySelector'

export type BalanceDisplayState = 'idle' | 'loading' | 'success' | 'error'

export interface TotalBalanceCardProps {
  currency: CurrencyCode
  total?: string
  valuationDate?: string | null
  state: BalanceDisplayState
}

function TotalBalanceCard({
  currency,
  total,
  valuationDate,
  state,
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
          {valuationDate && <p className="valuation-date">Valued {valuationDate}</p>}
        </div>
      )}
      {state === 'error' && (
        <p className="empty-message">The total balance is not available yet.</p>
      )}
    </section>
  )
}

export default TotalBalanceCard
