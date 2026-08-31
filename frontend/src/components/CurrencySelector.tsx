import type { ChangeEvent } from 'react'

import type { CurrencyCode } from '../api/types'

export type { CurrencyCode } from '../api/types'

export interface CurrencyOption {
  value: CurrencyCode
  label: string
}

export interface CurrencySelectorProps {
  id: string
  label: string
  value: CurrencyCode
  options: readonly CurrencyOption[]
  onChange: (value: CurrencyCode) => void
  className?: string
}

function CurrencySelector({
  id,
  label,
  value,
  options,
  onChange,
  className,
}: CurrencySelectorProps) {
  const handleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const selectedOption = options.find(
      (option) => option.value === event.currentTarget.value,
    )

    if (selectedOption) {
      onChange(selectedOption.value)
    }
  }

  return (
    <div className={`field-group currency-selector${className ? ` ${className}` : ''}`}>
      <label htmlFor={id}>{label}</label>
      <select
        id={id}
        name={id}
        value={value}
        onChange={handleChange}
        disabled={options.length === 0}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  )
}

export default CurrencySelector
