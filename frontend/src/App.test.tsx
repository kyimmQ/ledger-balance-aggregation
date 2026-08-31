import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  it('renders the ledger dashboard shell and key controls', () => {
    render(<App />)

    expect(
      screen.getByRole('heading', { name: 'See the balance behind every account' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Display currency' })).toHaveValue('USD')
    expect(screen.getByRole('textbox', { name: 'Account ID' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Look up balance' })).toBeInTheDocument()
    expect(
      screen.getByText('Your combined balance will appear here after a ledger request.'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('Search for an account to see its stored balance and valuation date.'),
    ).toBeInTheDocument()
  })
})
