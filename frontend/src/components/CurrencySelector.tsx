import type { ChangeEvent } from 'react'

export type CurrencyCode = 'USD' | 'EUR' | 'GBP'

export interface CurrencyOption {
  value: CurrencyCode
  label: string
}

export interface CurrencySelectorProps {
  value: CurrencyCode
  options: readonly CurrencyOption[]
  onChange: (value: CurrencyCode) => void
}

function CurrencySelector({ value, options, onChange }: CurrencySelectorProps) {
  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const selectedOption = options.find(
      (option) => option.value === event.currentTarget.value,
    )

    if (selectedOption) {
      onChange(selectedOption.value)
    }
  }

  return (
    <div className="field-group">
      <label htmlFor="currency">Display currency</label>
      <select
        id="currency"
        name="currency"
        value={value}
        onChange={handleChange}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      <p className="field-description" id="currency-description">
        Choose the currency used when the ledger returns a balance.
      </p>
    </div>
  )
}

export default CurrencySelector
