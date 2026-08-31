import type { CurrencyCode } from './CurrencySelector'
import type { BalanceDisplayState } from './TotalBalanceCard'

export interface AccountBalanceCardProps {
  accountId?: string | number
  accountName?: string
  currency: CurrencyCode
  balance?: string
  valuationDate?: string | null
  state: BalanceDisplayState
}

function AccountBalanceCard({
  accountId,
  accountName,
  currency,
  balance,
  valuationDate,
  state,
}: AccountBalanceCardProps) {
  return (
    <section className={`card account-card state-${state}`} aria-labelledby="account-balance-heading">
      <div className="card-heading-row">
        <div>
          <p className="card-kicker">Account detail</p>
          <h2 id="account-balance-heading">Account balance</h2>
        </div>
        <span className="currency-chip">{currency}</span>
      </div>
      {state === 'idle' && (
        <p className="empty-message">
          Search for an account to see its stored balance and valuation date.
        </p>
      )}
      {state === 'loading' && (
        <p className="loading-message" role="status" aria-live="polite">
          Loading account balance…
        </p>
      )}
      {state === 'success' && balance !== undefined && (
        <div className="balance-result">
          {(accountId !== undefined || accountName) && (
            <p className="account-identity">
              {accountName ?? 'Account'}
              {accountId !== undefined && <span> · ID {accountId}</span>}
            </p>
          )}
          <p className="money-value">{balance}</p>
          <p className="valuation-date">
            {valuationDate
              ? `Valued ${valuationDate}`
              : currency === 'USD'
                ? 'Stored USD'
                : 'Valuation date unavailable'}
          </p>
        </div>
      )}
      {state === 'error' && (
        <p className="empty-message">An account balance will appear after a successful lookup.</p>
      )}
    </section>
  )
}

export default AccountBalanceCard
