import { useEffect, useRef } from 'react'

import type { AccountBalance } from '../api/types'
import { type BalanceDisplayState, getMoneyTone } from './balancePresentation'

export interface AccountBalanceTableProps {
  account?: AccountBalance
  state: BalanceDisplayState
  message?: string
  pending?: boolean
  onRetry?: () => void
}

function AccountBalanceTable({
  account,
  state,
  message,
  pending = state === 'loading' || state === 'refreshing',
  onRetry,
}: AccountBalanceTableProps) {
  const resultsRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (state !== 'success' || account === undefined) {
      return
    }

    const reduceMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false
    resultsRef.current?.scrollIntoView?.({
      behavior: reduceMotion ? 'auto' : 'smooth',
      block: 'center',
    })
  }, [account, state])

  if (state === 'idle' || state === 'not-found') {
    return null
  }

  const hasValue = (state === 'success' || state === 'refreshing') && account
  const valueTone = account ? getMoneyTone(account.balance) : 'normal'

  return (
    <div ref={resultsRef} className={`account-results state-${state}`} aria-busy={pending}>
      <table className="balance-table">
        <caption>Account balance result</caption>
        <thead>
          <tr>
            <th scope="col">Account</th>
            <th scope="col">Balance</th>
          </tr>
        </thead>
        <tbody>
          {hasValue && (
            <tr>
              <th scope="row">
                {account.name}
                <span className="table-secondary">ID {account.accountId}</span>
              </th>
              <td className={`money-${valueTone}`}>
                {account.balance}
                <span className="table-secondary">{account.currency}</span>
              </td>
            </tr>
          )}
          {!hasValue && (
            <tr>
              <td colSpan={2}>
                <div
                  className="table-state"
                  {...(state === 'error'
                    ? { role: 'group', 'aria-label': 'Account balance request result' }
                    : state === 'loading' || state === 'refreshing'
                      ? { role: 'status', 'aria-live': 'polite' as const }
                      : {})}
                >
                  <p>
                    {state === 'loading'
                        ? 'Loading account balance…'
                        : state === 'refreshing'
                          ? 'Refreshing account balance…'
                          : message ?? getDefaultMessage(state)}
                  </p>
                  {(state === 'empty' || state === 'error') && onRetry && (
                    <button type="button" className="retry-button" onClick={onRetry}>
                      Retry account balance
                    </button>
                  )}
                </div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function getDefaultMessage(state: BalanceDisplayState): string {
  if (state === 'empty') {
    return 'The ledger dataset is not available right now.'
  }
  return 'An account balance is not available yet.'
}

export default AccountBalanceTable
