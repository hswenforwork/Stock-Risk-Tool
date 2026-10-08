import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, test, vi } from 'vitest'
import App from './App'

const REPORT = {
  initial_capital: 1_000_000,
  final_equity: 1_123_400,
  total_return: 0.1234,
  trades: [
    {
      date: '2021-02-01',
      action: 'entry',
      shares: 1990,
      price: 500.5,
      fee: 851,
      tax: 0,
      delayed: false,
    },
    {
      date: '2021-03-15',
      action: 'exit',
      shares: 1990,
      price: 560.44,
      fee: 953,
      tax: 3345,
      delayed: true,
    },
  ],
}

function stubFetch(body: unknown, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function sentBody(fetchMock: ReturnType<typeof vi.fn>) {
  return JSON.parse(fetchMock.mock.calls[0][1].body as string)
}

afterEach(() => {
  vi.unstubAllGlobals()
})

test('按下回測後顯示總報酬與交易明細', async () => {
  const fetchMock = stubFetch(REPORT)

  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: '回測' }))

  expect(await screen.findByText('+12.34%')).toBeInTheDocument()
  expect(fetchMock).toHaveBeenCalledWith(
    '/api/backtests',
    expect.objectContaining({ method: 'POST' }),
  )

  const rows = within(screen.getByRole('table', { name: '交易明細' })).getAllByRole('row')
  expect(rows).toHaveLength(3) // 表頭 + 2 筆
  expect(rows[1]).toHaveTextContent('2021-02-01')
  expect(rows[1]).toHaveTextContent('進場')
  expect(rows[1]).toHaveTextContent('1,990')
  expect(rows[2]).toHaveTextContent('出場')
  expect(rows[2]).toHaveTextContent('3,345')
  expect(rows[2]).toHaveTextContent('延後')
})

test('預設以零股成交，可以改成整張', async () => {
  const fetchMock = stubFetch(REPORT)

  render(<App />)
  await userEvent.selectOptions(screen.getByLabelText('成交單位'), '整張')
  await userEvent.click(screen.getByRole('button', { name: '回測' }))

  expect(sentBody(fetchMock).lot).toBe('board')
})

test('起始日早於 2020-10-26 時顯示說明且不能回測', async () => {
  stubFetch(REPORT)

  render(<App />)
  const startDate = screen.getByLabelText('起始日')
  expect(startDate).toHaveAttribute('min', '2020-10-26')

  await userEvent.clear(startDate)
  await userEvent.type(startDate, '2020-01-02')

  expect(screen.getByRole('alert')).toHaveTextContent('盤中零股交易 2020-10-26 才開放')
  expect(screen.getByRole('button', { name: '回測' })).toBeDisabled()
})

test('回測區間會送到後端', async () => {
  const fetchMock = stubFetch(REPORT)

  render(<App />)
  await userEvent.type(screen.getByLabelText('起始日'), '2021-01-04')
  await userEvent.type(screen.getByLabelText('結束日'), '2021-06-30')
  await userEvent.click(screen.getByRole('button', { name: '回測' }))

  expect(sentBody(fetchMock)).toMatchObject({ start_date: '2021-01-04', end_date: '2021-06-30' })
})

test('後端拒絕設定時顯示原因', async () => {
  stubFetch(
    { detail: [{ msg: 'Value error, 回測結束日不得早於起始日' }] },
    422,
  )

  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: '回測' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('回測結束日不得早於起始日')
})

test('回測失敗時顯示錯誤訊息', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('error', { status: 500 })))

  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: '回測' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('回測失敗')
})
