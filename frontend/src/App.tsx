import { useEffect, useState, type FormEvent } from 'react'

import AccountBalanceTable from './components/AccountBalanceTable'
import AccountLookupForm from './components/AccountLookupForm'
import FeedbackMessage from './components/FeedbackMessage'
import Footer from './components/Footer'
import Header from './components/Header'
import TotalBalanceCard from './components/TotalBalanceCard'
import type { AsyncState } from './api/state'
import type { AccountBalance, TotalBalance } from './api/types'
import { getLedgerQueryError, useLedgerQueries } from './hooks/useLedgerQueries'
import { useSupportedCurrencies } from './hooks/useSupportedCurrencies'
import './App.css'

function App() {
  const {
    totalCurrency,
    accountCurrency,
    totalState,
    accountState,
    lookupAccount,
    changeTotalCurrency,
    changeAccountCurrency,
    retryTotal,
    retryAccount,
  } = useLedgerQueries()
  const currenciesState = useSupportedCurrencies()
  const [accountId, setAccountId] = useState('')

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    lookupAccount(accountId)
  }

  const handleAccountIdChange = (nextAccountId: string) => {
    setAccountId(nextAccountId)
  }

  const totalError = totalState.status === 'error'
    ? getLedgerQueryError(totalState.error)
    : undefined
  const accountError = accountState.status === 'error'
    ? getLedgerQueryError(accountState.error)
    : undefined
  const currenciesError = currenciesState.status === 'error'
    ? getLedgerQueryError(currenciesState.error)
    : undefined
  const totalPending = totalState.status === 'loading' || totalState.status === 'refreshing'
  const accountPending = accountState.status === 'loading' || accountState.status === 'refreshing'
  const currenciesPending = currenciesState.status === 'loading'
  const supportedCurrencies = currenciesState.status === 'success'
    ? currenciesState.data.currencies.map((currency) => ({ value: currency, label: currency }))
    : []
  const showFeedback = !totalPending && !accountPending && !currenciesPending && Boolean(
    currenciesError || accountError || totalError || totalState.status === 'success' || accountState.status === 'success',
  )
  const feedbackTone = currenciesError || accountError || totalError
    ? 'error' as const
    : 'success' as const
  const feedbackText = getFeedbackMessage({
    currenciesError,
    accountError,
    totalError,
    accountState,
    totalState,
  })
  const feedbackKey = `${feedbackTone}:${feedbackText}`

  useEffect(() => {
    document.title = 'Ledger balance dashboard'
  }, [])

  return (
    <div className="app-shell">
      <Header />
      <main className="page-width main-content" aria-labelledby="dashboard-heading">
        {showFeedback && (
          <FeedbackMessage
            key={feedbackKey}
            tone={feedbackTone}
            message={feedbackText}
            announce={!totalPending && !accountPending}
          />
        )}
        <div className="intro-copy">
          <p className="eyebrow">Ledger workspace</p>
          <h2 id="dashboard-heading">A clear view of your balances</h2>
          <p>
            Choose a currency for the portfolio total, then look up an account in
            its own currency. Results come directly from the ledger.
          </p>
        </div>

        <div className="dashboard-grid">
          <aside className="total-summary" aria-label="Total summary">
            <TotalBalanceCard
              currency={totalCurrency}
              state={getBalanceDisplayState(totalState)}
              total={hasTotalData(totalState) ? totalState.data.total : undefined}
              message={totalError?.message}
              pending={totalPending}
              onRetry={retryTotal}
              currencyOptions={supportedCurrencies}
              onCurrencyChange={changeTotalCurrency}
            />
          </aside>

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
              currency={accountCurrency}
              currencyOptions={supportedCurrencies}
              onCurrencyChange={changeAccountCurrency}
            />
            <AccountBalanceTable
              state={getBalanceDisplayState(accountState)}
              account={hasAccountData(accountState) ? accountState.data : undefined}
              message={accountError?.message}
              pending={accountPending}
              onRetry={retryAccount}
            />
          </section>
        </div>
      </main>
      <Footer />
    </div>
  )
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
  currenciesError,
  accountError,
  totalError,
  accountState,
  totalState,
}: {
  currenciesError?: { message: string }
  accountError?: { message: string }
  totalError?: { message: string }
  accountState: { status: string }
  totalState: { status: string }
}): string {
  if (currenciesError) {
    return currenciesError.message
  }
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
