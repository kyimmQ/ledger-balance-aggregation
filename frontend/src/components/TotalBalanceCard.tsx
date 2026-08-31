import CurrencySelector, { type CurrencyCode, type CurrencyOption } from './CurrencySelector'
import { type BalanceDisplayState, getMoneyTone } from './balancePresentation'

export type { BalanceDisplayState } from './balancePresentation'

export interface TotalBalanceCardProps {
  currency: CurrencyCode
  total?: string
  state: BalanceDisplayState
  message?: string
  pending?: boolean
  onRetry?: () => void
  currencyOptions: readonly CurrencyOption[]
  onCurrencyChange: (currency: CurrencyCode) => void
}

function TotalBalanceCard({
  currency,
  total,
  state,
  message,
  pending = state === 'loading' || state === 'refreshing',
  onRetry,
  currencyOptions,
  onCurrencyChange,
}: TotalBalanceCardProps) {
  const hasValue = state === 'success' || state === 'refreshing'
  const valueTone = total === undefined ? 'normal' : getMoneyTone(total)
  const valueSize = total === undefined ? 'regular' : getTotalSize(total)

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
        <CurrencySelector
          id="total-currency"
          label="Currency"
          value={currency}
          options={currencyOptions}
          onChange={onCurrencyChange}
          className="currency-selector-compact"
        />
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
          <p className={`money-value total-money-${valueSize} money-${valueTone}`}>
            <span>{total}</span>
          </p>
          <p className="balance-currency">{currency}</p>
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

function getTotalSize(value: string): 'regular' | 'compact' | 'long' {
  const digitCount = value.replace(/[^0-9]/g, '').length
  if (digitCount > 18) {
    return 'long'
  }
  if (digitCount > 12) {
    return 'compact'
  }
  return 'regular'
}

export default TotalBalanceCard
