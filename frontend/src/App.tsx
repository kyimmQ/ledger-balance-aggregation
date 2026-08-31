import { useState, type FormEvent } from 'react'

import AccountBalanceCard from './components/AccountBalanceCard'
import AccountLookupForm from './components/AccountLookupForm'
import CurrencySelector, {
  type CurrencyCode,
} from './components/CurrencySelector'
import FeedbackMessage from './components/FeedbackMessage'
import Footer from './components/Footer'
import Header from './components/Header'
import TotalBalanceCard from './components/TotalBalanceCard'
import './App.css'

const supportedCurrencies = [
  { value: 'USD' as const, label: 'USD — US dollar' },
  { value: 'EUR' as const, label: 'EUR — euro' },
  { value: 'GBP' as const, label: 'GBP — British pound' },
]

function App() {
  const [currency, setCurrency] = useState<CurrencyCode>('USD')
  const [accountId, setAccountId] = useState('')

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
  }

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
          <TotalBalanceCard currency={currency} state="idle" />

          <section className="card lookup-card" aria-labelledby="lookup-heading">
            <div className="card-heading-row">
              <div>
                <p className="card-kicker">Find a record</p>
                <h2 id="lookup-heading">Account lookup</h2>
              </div>
            </div>
            <AccountLookupForm
              accountId={accountId}
              onAccountIdChange={setAccountId}
              onSubmit={handleSubmit}
              disabled={false}
            />
            <CurrencySelector
              value={currency}
              options={supportedCurrencies}
              onChange={setCurrency}
            />
          </section>

          <AccountBalanceCard currency={currency} state="idle" />
        </div>

        <FeedbackMessage
          tone="info"
          message="No request has been made yet. Account and total cards will fill with ledger data after the lookup workflow is connected."
        />
      </main>
      <Footer />
    </div>
  )
}

export default App
