import type { CurrencyCode } from './CurrencySelector'
import type { BalanceDisplayState } from './TotalBalanceCard'

export interface AccountBalanceCardProps {
  accountId?: string | number
  accountName?: string
  currency: CurrencyCode
  balance?: string
  valuationDate?: string | null
  state: BalanceDisplayState
  message?: string
}

function AccountBalanceCard({
  accountId,
  accountName,
  currency,
  balance,
  valuationDate,
  state,
  message,
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
  if (state === 'not-found') {
    return 'That account was not found in the current ledger.'
  }
  if (state === 'empty') {
    return 'The ledger dataset is not available right now.'
  }
  return 'An account balance is not available yet.'
}

export default AccountBalanceCard
