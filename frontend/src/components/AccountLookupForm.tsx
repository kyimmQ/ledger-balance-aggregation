import type { FormEvent } from 'react'

export interface AccountLookupFormProps {
  accountId: string
  onAccountIdChange: (accountId: string) => void
  onSubmit: (event: FormEvent<HTMLFormElement>) => void
  disabled: boolean
  pending?: boolean
  validationMessage?: string
}

function AccountLookupForm({
  accountId,
  onAccountIdChange,
  onSubmit,
  disabled,
  pending = false,
  validationMessage,
}: AccountLookupFormProps) {
  const describedBy = validationMessage
    ? 'account-id-hint account-id-validation'
    : 'account-id-hint'

  return (
    <form className="lookup-form" onSubmit={onSubmit} noValidate aria-busy={pending}>
      <div className="field-group">
        <label htmlFor="account-id">Account ID</label>
        <input
          id="account-id"
          name="accountId"
          type="text"
          inputMode="numeric"
          value={accountId}
          onChange={(event) => onAccountIdChange(event.currentTarget.value)}
          disabled={disabled}
          aria-describedby={describedBy}
          aria-invalid={validationMessage ? true : undefined}
          autoComplete="off"
        />
        <p className="field-description" id="account-id-hint">
          Enter the account identifier from the ledger, for example 100.
        </p>
        {validationMessage && (
          <p className="validation-message" id="account-id-validation">
            {validationMessage}
          </p>
        )}
      </div>
      <button type="submit" disabled={disabled}>
        Look up balance
      </button>
    </form>
  )
}

export default AccountLookupForm
