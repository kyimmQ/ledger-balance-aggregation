import type { FormEvent } from 'react'

import CurrencySelector, { type CurrencyCode, type CurrencyOption } from './CurrencySelector'

export interface AccountLookupFormProps {
  accountId: string
  onAccountIdChange: (accountId: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  disabled: boolean
  pending?: boolean
  currency: CurrencyCode
  currencyOptions: readonly CurrencyOption[]
  onCurrencyChange: (currency: CurrencyCode) => void
}

function AccountLookupForm({
  accountId,
  onAccountIdChange,
  onSubmit,
  disabled,
  pending = false,
  currency,
  currencyOptions,
  onCurrencyChange,
}: AccountLookupFormProps) {
  return (
    <form className="lookup-form" onSubmit={onSubmit} noValidate aria-busy={pending}>
      <div className="lookup-controls">
        <div className="field-group">
          <label htmlFor="account-id">Account ID</label>
          <input
            id="account-id"
            name="accountId"
            type="text"
            inputMode="numeric"
            placeholder="e.g. 100"
            value={accountId}
            onChange={(event) => onAccountIdChange(event.currentTarget.value)}
            disabled={disabled}
            autoComplete="off"
          />
        </div>
        <CurrencySelector
          id="account-currency"
          label="Currency"
          value={currency}
          options={currencyOptions}
          onChange={onCurrencyChange}
          className="currency-selector-compact"
        />
      </div>
      <button type="submit" disabled={disabled}>
        Look up balance
      </button>
    </form>
  )
}

export default AccountLookupForm
