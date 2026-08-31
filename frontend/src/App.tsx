import { useEffect, useState, type FormEvent } from 'react'

import AccountBalanceCard from './components/AccountBalanceCard'
import AccountLookupForm from './components/AccountLookupForm'
import CurrencySelector from './components/CurrencySelector'
import FeedbackMessage from './components/FeedbackMessage'
import Footer from './components/Footer'
import Header from './components/Header'
import TotalBalanceCard from './components/TotalBalanceCard'
import type { AsyncState } from './api/state'
import type { AccountBalance, TotalBalance } from './api/types'
import { getLedgerQueryError, useLedgerQueries } from './hooks/useLedgerQueries'
import './App.css'

const supportedCurrencies = [
  { value: 'USD' as const, label: 'USD — US dollar' },
  { value: 'EUR' as const, label: 'EUR — euro' },
  { value: 'GBP' as const, label: 'GBP — British pound' },
]

function App() {
  const {
    currency,
    totalState,
    accountState,
    lookupAccount,
    changeCurrency,
    retryTotal,
    retryAccount,
  } = useLedgerQueries()
  const [accountId, setAccountId] = useState('')
  const [validationMessage, setValidationMessage] = useState<string>()

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (!/^[0-9]+$/.test(accountId) || !isValidAccountId(accountId)) {
      setValidationMessage('Enter an account ID between 100 and 999.')
      return
    }

    setValidationMessage(undefined)
    lookupAccount(accountId)
  }

  const handleAccountIdChange = (nextAccountId: string) => {
    setAccountId(nextAccountId)
    if (validationMessage) {
      setValidationMessage(undefined)
    }
  }

  const totalError = totalState.status === 'error'
    ? getLedgerQueryError(totalState.error)
    : undefined
  const accountError = accountState.status === 'error'
    ? getLedgerQueryError(accountState.error)
    : undefined
  const totalPending = totalState.status === 'loading' || totalState.status === 'refreshing'
  const accountPending = accountState.status === 'loading' || accountState.status === 'refreshing'

  useEffect(() => {
    document.title = 'Ledger balance dashboard'
  }, [])

  return (
    <div className="app-shell">
      <Header />
      <main className="page-width main-content" aria-labelledby="dashboard-heading">
        <div className="intro-copy">
          <p className="eyebrow">Ledger workspace</p>
          <h2 id="dashboard-heading">A clear view of your balances</h2>
          <p>
            Choose a display currency and look up an account when you are ready.
            Results come directly from the ledger.
          </p>
        </div>

        <div className="dashboard-grid">
          <TotalBalanceCard
            currency={currency}
            state={getBalanceDisplayState(totalState)}
            total={hasTotalData(totalState) ? totalState.data.total : undefined}
            valuationDate={
              hasTotalData(totalState) ? totalState.data.valuationDate : undefined
            }
            message={totalError?.message}
            pending={totalPending}
            onRetry={retryTotal}
          />

          <section className="card lookup-card" aria-labelledby="lookup-heading">
            <div className="card-heading-row">
              <div>
                <p className="card-kicker">Find a record</p>
                <h2 id="lookup-heading">Account lookup</h2>
              </div>
            </div>
            <AccountLookupForm
              accountId={accountId}
              onAccountIdChange={handleAccountIdChange}
              onSubmit={handleSubmit}
              disabled={accountPending}
              pending={accountPending}
              validationMessage={validationMessage}
            />
            <CurrencySelector
              value={currency}
              options={supportedCurrencies}
              onChange={changeCurrency}
            />
          </section>

          <AccountBalanceCard
            currency={currency}
            state={getBalanceDisplayState(accountState)}
            accountId={hasAccountData(accountState) ? accountState.data.accountId : undefined}
            accountName={hasAccountData(accountState) ? accountState.data.name : undefined}
            balance={hasAccountData(accountState) ? accountState.data.balance : undefined}
            valuationDate={
              hasAccountData(accountState) ? accountState.data.valuationDate : undefined
            }
            message={accountError?.message}
            pending={accountPending}
            onRetry={retryAccount}
          />
        </div>

        <FeedbackMessage
          tone={accountError || totalError ? 'error' : totalState.status === 'success' ? 'success' : 'info'}
          message={getFeedbackMessage({
          accountError,
          totalError,
            accountState,
            totalState,
          })}
          announce={!totalPending && !accountPending}
        />
      </main>
      <Footer />
    </div>
  )
}

function isValidAccountId(accountId: string): boolean {
  const value = Number(accountId)
  return Number.isInteger(value) && value >= 100 && value <= 999
}

function getBalanceDisplayState(
  state: AsyncState<unknown>,
): 'idle' | 'loading' | 'refreshing' | 'success' | 'not-found' | 'empty' | 'error' {
  if (state.status !== 'error') {
    return state.status
  }

  const code = getLedgerQueryError(state.error).code
  if (code === 'ACCOUNT_NOT_FOUND') {
    return 'not-found'
  }
  if (code === 'DATASET_NOT_READY') {
    return 'empty'
  }
  return 'error'
}

function hasTotalData(
  state: AsyncState<TotalBalance>,
): state is { status: 'refreshing' | 'success'; data: TotalBalance } {
  return state.status === 'success' || state.status === 'refreshing'
}

function hasAccountData(
  state: AsyncState<AccountBalance>,
): state is { status: 'refreshing' | 'success'; data: AccountBalance } {
  return state.status === 'success' || state.status === 'refreshing'
}

function getFeedbackMessage({
  accountError,
  totalError,
  accountState,
  totalState,
}: {
  accountError?: { message: string }
  totalError?: { message: string }
  accountState: { status: string }
  totalState: { status: string }
}): string {
  if (accountError) {
    return accountError.message
  }
  if (totalError) {
    return totalError.message
  }
  if (accountState.status === 'loading' || totalState.status === 'loading') {
    return 'Loading the latest ledger balances…'
  }
  if (accountState.status === 'refreshing' || totalState.status === 'refreshing') {
    return 'Refreshing the latest ledger balances…'
  }
  if (accountState.status === 'success') {
    return 'Account balance loaded from the ledger.'
  }
  if (totalState.status === 'success') {
    return 'Total balance loaded from the ledger. Look up an account for its details.'
  }
  return 'Balances will appear here after a ledger request.'
}

export default App
