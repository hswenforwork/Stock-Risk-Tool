import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

afterEach(() => {
  vi.unstubAllGlobals()
})

test('按下回測後顯示總報酬', async () => {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(
      JSON.stringify({ initial_capital: 1_000_000, final_equity: 1_123_400, total_return: 0.1234 }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ),
  )
  vi.stubGlobal('fetch', fetchMock)

  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: '回測' }))

  expect(await screen.findByText('+12.34%')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/backtests',
    expect.objectContaining({ method: 'POST' }),
  )
})

test('回測失敗時顯示錯誤訊息', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('error', { status: 500 })))

  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: '回測' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('回測失敗')
})
