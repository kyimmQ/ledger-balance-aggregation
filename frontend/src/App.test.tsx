import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import App from './App'

function mockResponse(status: number, body: unknown): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: vi.fn().mockResolvedValue(body),
  } as unknown as Response
}

const total = (currency: string, value: string, valuationDate: string | null = null) => ({
  currency,
  total: value,
  valuationDate,
})

const account = (
  accountId: number,
  currency: string,
  balance: string,
  valuationDate: string | null = null,
) => ({
  accountId,
  name: `acct${accountId}`,
  currency,
  balance,
  valuationDate,
})

describe('ledger dashboard workflows', () => {
  const fetchMock = vi.fn<typeof fetch>()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
    vi.stubEnv('VITE_API_BASE_URL', '')
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllEnvs()
  })

  it('loads the USD total on mount and preserves its money string', async () => {
    fetchMock.mockResolvedValueOnce(mockResponse(200, total('USD', '0.005')))

    render(<App />)

    expect(await screen.findByText('0.005')).toBeInTheDocument()
    expect(screen.getByText('Stored USD')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/balances/total?currency=USD',
      expect.objectContaining({ cache: 'no-store', signal: expect.any(AbortSignal) }),
    )
  })

  it('submits a valid account through the native Enter path', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse(200, total('USD', '234.50')))
      .mockResolvedValueOnce(mockResponse(200, account(100, 'USD', '-12.30')))
    const user = userEvent.setup()

    render(<App />)
    const input = screen.getByRole('textbox', { name: 'Account ID' })
    await user.type(input, '100')
    await user.keyboard('{Enter}')

    expect(await screen.findByText('acct100')).toBeInTheDocument()
    expect(screen.getByText(/ID 100/)).toBeInTheDocument()
    expect(screen.getByText('-12.30')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/accounts/100/balance?currency=USD',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('refreshes the total and last account when currency changes', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse(200, total('USD', '100.00')))
      .mockResolvedValueOnce(mockResponse(200, account(100, 'USD', '10.00')))
      .mockResolvedValueOnce(mockResponse(200, total('EUR', '91.00', '2026-06-18')))
      .mockResolvedValueOnce(mockResponse(200, account(100, 'EUR', '9.10', '2026-06-18')))
    const user = userEvent.setup()

    render(<App />)
    await screen.findByText('100.00')
    await user.type(screen.getByRole('textbox', { name: 'Account ID' }), '100')
    await user.click(screen.getByRole('button', { name: 'Look up balance' }))
    await screen.findByText('10.00')

    await user.selectOptions(screen.getByRole('combobox', { name: 'Display currency' }), 'EUR')

    expect(await screen.findByText('91.00')).toBeInTheDocument()
    expect(await screen.findByText('9.10')).toBeInTheDocument()
    expect(screen.getAllByText('Valued 2026-06-18')).toHaveLength(2)
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/accounts/100/balance?currency=EUR',
      expect.anything(),
    )
  })

  it('shows inline validation and does not call the API for an invalid account ID', async () => {
    fetchMock.mockResolvedValueOnce(mockResponse(200, total('USD', '100.00')))
    const user = userEvent.setup()

    render(<App />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const input = screen.getByRole('textbox', { name: 'Account ID' })
    await user.type(input, '99')
    await user.click(screen.getByRole('button', { name: 'Look up balance' }))

    expect(screen.getByText('Enter an account ID between 100 and 999.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('disables duplicate account submits while the request is pending', async () => {
    let resolveAccount!: (response: Response) => void
    fetchMock
      .mockResolvedValueOnce(mockResponse(200, total('USD', '100.00')))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveAccount = resolve }))
    const user = userEvent.setup()

    render(<App />)
    await user.type(screen.getByRole('textbox', { name: 'Account ID' }), '100')
    const submit = screen.getByRole('button', { name: 'Look up balance' })
    await user.click(submit)
    expect(submit).toBeDisabled()
    expect(fetchMock).toHaveBeenCalledTimes(2)

    resolveAccount(mockResponse(200, account(100, 'USD', '10.00')))
    expect(await screen.findByText('10.00')).toBeInTheDocument()
  })

  it('renders a safe account-not-found message', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse(200, total('USD', '100.00')))
      .mockResolvedValueOnce(mockResponse(404, {
        error: {
          code: 'ACCOUNT_NOT_FOUND',
          message: 'Account 999 was not found',
          requestId: 'private-request-id',
        },
      }))
    const user = userEvent.setup()

    render(<App />)
    await user.type(screen.getByRole('textbox', { name: 'Account ID' }), '999')
    await user.click(screen.getByRole('button', { name: 'Look up balance' }))

    expect(await screen.findAllByText('That account was not found in the current ledger.')).toHaveLength(2)
    expect(screen.queryByText('Account 999 was not found')).not.toBeInTheDocument()
    expect(screen.queryByText('private-request-id')).not.toBeInTheDocument()
  })

  it('renders a distinct network failure message', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse(200, total('USD', '100.00')))
      .mockRejectedValueOnce(new TypeError('private socket details'))
    const user = userEvent.setup()

    render(<App />)
    await user.type(screen.getByRole('textbox', { name: 'Account ID' }), '100')
    await user.click(screen.getByRole('button', { name: 'Look up balance' }))

    expect(await screen.findAllByText('Unable to reach the ledger service. Please try again.')).toHaveLength(2)
    expect(screen.queryByText('private socket details')).not.toBeInTheDocument()
  })

  it('does not let an older account response overwrite a newer currency response', async () => {
    let resolveTotal!: (response: Response) => void
    let resolveUsdAccount!: (response: Response) => void
    let resolveEurTotal!: (response: Response) => void
    let resolveEurAccount!: (response: Response) => void
    fetchMock
      .mockImplementationOnce(() => new Promise((resolve) => { resolveTotal = resolve }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveUsdAccount = resolve }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveEurTotal = resolve }))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveEurAccount = resolve }))
    const user = userEvent.setup()

    render(<App />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    resolveTotal(mockResponse(200, total('USD', '100.00')))
    await screen.findByText('100.00')
    await user.type(screen.getByRole('textbox', { name: 'Account ID' }), '100')
    await user.click(screen.getByRole('button', { name: 'Look up balance' }))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Display currency' }), 'EUR')

    resolveEurTotal(mockResponse(200, total('EUR', '90.00', '2026-06-18')))
    resolveEurAccount(mockResponse(200, account(100, 'EUR', '9.00', '2026-06-18')))
    expect(await screen.findByText('9.00')).toBeInTheDocument()
    resolveUsdAccount(mockResponse(200, account(100, 'USD', '1.00')))

    await waitFor(() => expect(screen.getByText('9.00')).toBeInTheDocument())
    expect(screen.queryByText('1.00')).not.toBeInTheDocument()
  })

  it('retries only the failed total request through keyboard activation', async () => {
    fetchMock
      .mockRejectedValueOnce(new TypeError('temporary network failure'))
      .mockResolvedValueOnce(mockResponse(200, total('USD', '125.00')))
    const user = userEvent.setup()

    render(<App />)

    const retry = await screen.findByRole('button', { name: 'Retry total balance' })
    expect(screen.getByRole('alert')).toHaveTextContent(
      'Unable to reach the ledger service. Please try again.',
    )
    retry.focus()
    await user.keyboard('{Enter}')

    expect(await screen.findByText('125.00')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/balances/total?currency=USD',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('shows an empty-dataset state and retries the total request', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse(503, {
        error: {
          code: 'DATASET_NOT_READY',
          message: 'No balance dataset is currently available',
          requestId: 'dataset-request-id',
        },
      }))
      .mockResolvedValueOnce(mockResponse(200, total('USD', '125.00')))
    const user = userEvent.setup()

    render(<App />)

    const totalCard = screen.getByRole('region', { name: 'Total balance' })
    expect(await within(totalCard).findByText(
      'The ledger dataset is not available right now. Please try again later.',
    )).toBeInTheDocument()
    expect(totalCard).toHaveClass('state-empty')
    expect(screen.queryByText('125.00')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Retry total balance' }))

    expect(await screen.findByText('125.00')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('retries only the failed account request and keeps the selected account', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse(200, total('USD', '125.00')))
      .mockRejectedValueOnce(new TypeError('temporary network failure'))
      .mockResolvedValueOnce(mockResponse(200, account(100, 'USD', '0.00')))
    const user = userEvent.setup()

    render(<App />)
    const input = screen.getByRole('textbox', { name: 'Account ID' })
    await user.type(input, '100')
    await user.click(screen.getByRole('button', { name: 'Look up balance' }))

    const retry = await screen.findByRole('button', { name: 'Retry account balance' })
    await user.click(retry)

    expect(await screen.findByText('0.00')).toBeInTheDocument()
    expect(screen.getByText('Zero balance')).toBeInTheDocument()
    expect(screen.getByDisplayValue('100')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(fetchMock).toHaveBeenLastCalledWith(
      '/api/accounts/100/balance?currency=USD',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('retains a valid total while a same-currency retry is refreshing', async () => {
    let resolveRetry!: (response: Response) => void
    fetchMock
      .mockRejectedValueOnce(new TypeError('temporary network failure'))
      .mockResolvedValueOnce(mockResponse(200, total('USD', '100.00')))
      .mockImplementationOnce(() => new Promise((resolve) => { resolveRetry = resolve }))
    const user = userEvent.setup()

    render(<App />)
    await user.click(await screen.findByRole('button', { name: 'Retry total balance' }))
    await screen.findByText('100.00')
    await user.click(screen.getByRole('button', { name: 'Refresh total balance' }))

    expect(screen.getByText('100.00')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Refreshing total balance…')
    expect(screen.getByRole('region', { name: 'Total balance' })).toHaveAttribute('aria-busy', 'true')

    resolveRetry(mockResponse(200, total('USD', '101.00')))
    expect(await screen.findByText('101.00')).toBeInTheDocument()
  })

  it('marks negative balances without changing the API money string', async () => {
    fetchMock
      .mockResolvedValueOnce(mockResponse(200, total('USD', '0.00')))
      .mockResolvedValueOnce(mockResponse(200, account(100, 'USD', '-12.30')))
    const user = userEvent.setup()

    render(<App />)
    await user.type(screen.getByRole('textbox', { name: 'Account ID' }), '100')
    await user.click(screen.getByRole('button', { name: 'Look up balance' }))

    expect((await screen.findByText('-12.30')).closest('p')).toHaveClass('money-negative')
    expect(screen.getByText('Negative balance')).toBeInTheDocument()
    expect(screen.getByText('0.00').closest('p')).toHaveClass('money-zero')
    expect(screen.getByText('Zero balance')).toBeInTheDocument()
  })
})
