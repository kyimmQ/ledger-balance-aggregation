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
  pending?: boolean
  onRetry?: () => void
}

function AccountBalanceCard({
  accountId,
  accountName,
  currency,
  balance,
  valuationDate,
  state,
  message,
  pending = state === 'loading' || state === 'refreshing',
  onRetry,
}: AccountBalanceCardProps) {
  const hasValue = state === 'success' || state === 'refreshing'
  const valueTone = balance === undefined ? 'normal' : getMoneyTone(balance)

  return (
    <section
      className={`card account-card state-${state}`}
      aria-labelledby="account-balance-heading"
      aria-busy={pending}
    >
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
      {state === 'refreshing' && (
        <p className="loading-message refreshing-message" role="status" aria-live="polite">
          Refreshing account balance…
        </p>
      )}
      {hasValue && balance !== undefined && (
        <div className="balance-result">
          {(accountId !== undefined || accountName) && (
            <p className="account-identity">
              {accountName ?? 'Account'}
              {accountId !== undefined && <span> · ID {accountId}</span>}
            </p>
          )}
          <p className={`money-value money-${valueTone}`}>
            <span>{balance}</span>
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
              {state === 'refreshing' ? 'Refreshing account balance…' : 'Refresh account balance'}
            </button>
          )}
        </div>
      )}
      {(state === 'not-found' || state === 'empty' || state === 'error') && (
        <div className="error-content" role="group" aria-label="Account balance request result">
          <p className="empty-message">{message ?? getDefaultMessage(state)}</p>
          {state === 'error' && onRetry && (
            <button type="button" className="retry-button" onClick={onRetry}>
              Retry account balance
            </button>
          )}
        </div>
      )}
    </section>
  )
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
