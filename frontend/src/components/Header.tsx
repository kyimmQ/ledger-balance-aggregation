function Header() {
  return (
    <header className="site-header">
      <div className="page-width header-content">
        <div>
          <p className="brand-name">Ledger balance</p>
          <h1 id="page-title">See the balance behind every account</h1>
          <p className="header-subtitle">
            Look up a stored ledger balance in the currency you need.
          </p>
        </div>
        <span className="status-badge" aria-label="Ledger status: live ledger">
          <span className="status-dot" aria-hidden="true" />
          Live ledger
        </span>
      </div>
    </header>
  )
}

export default Header
