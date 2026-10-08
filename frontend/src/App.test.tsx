import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import App from './App'
import type { ConversionResult } from './strategy/convert'

// Blockly 需要真正的瀏覽器排版，這裡以假的編輯器代替；編輯器本身由 strategy/ 的測試涵蓋
const editor = vi.hoisted(() => ({ result: null as unknown }))
vi.mock('./strategy/StrategyEditor', () => ({
  StrategyEditor: ({ onChange }: { onChange: (r: ConversionResult) => void }) => {
    useEffect(() => onChange(editor.result as ConversionResult), [onChange])
    return <div>策略編輯器</div>
  },
}))

const STRATEGY = {
  version: 1,
  entry_ratios: [1],
  exit_ratios: [1],
  rules: [{ action: 'entry', condition: { type: 'rsi', op: 'below', period: 14, value: 30 } }],
}

beforeEach(() => {
  editor.result = { ok: true, strategy: STRATEGY, warnings: [] }
})

const REPORT = {
  initial_capital: 1_000_000,
  final_equity: 1_123_400,
  total_return: 0.1234,
  trades: [
    {
      date: '2021-02-01',
      action: 'entry',
      batch: 1,
      shares: 1990,
      price: 500.5,
      fee: 851,
      tax: 0,
      delayed: false,
    },
    {
      date: '2021-03-15',
      action: 'add',
      batch: 2,
      shares: 600,
      price: 520,
      fee: 266,
      tax: 0,
      delayed: false,
    },
    {
      date: '2021-04-01',
      action: 'exit',
      batch: 1,
      shares: 1290,
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
  expect(rows).toHaveLength(4) // 表頭 + 3 筆
  expect(rows[1]).toHaveTextContent('2021-02-01')
  expect(rows[1]).toHaveTextContent('進場')
  expect(rows[1]).toHaveTextContent('第 1 層')
  expect(rows[1]).toHaveTextContent('1,990')
  expect(rows[2]).toHaveTextContent('加碼')
  expect(rows[2]).toHaveTextContent('第 2 層')
  expect(rows[3]).toHaveTextContent('出場')
  expect(rows[3]).toHaveTextContent('第 1 批')
  expect(rows[3]).toHaveTextContent('3,345')
  expect(rows[3]).toHaveTextContent('延後')
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

test('送出編輯器產生的策略 JSON', async () => {
  const fetchMock = stubFetch(REPORT)

  render(<App />)
  await screen.findByText('策略編輯器') // 等延遲載入的編輯器回報策略
  await userEvent.click(screen.getByRole('button', { name: '回測' }))

  expect(sentBody(fetchMock).strategy).toEqual(STRATEGY)
})

test('策略不完整時列出問題且不能回測', async () => {
  editor.result = { ok: false, errors: ['第 1 條規則缺少條件。', '第 2 條規則缺少條件。'] }

  render(<App />)

  const problems = await screen.findByRole('list', { name: '策略的問題' })
  expect(within(problems).getAllByRole('listitem')).toHaveLength(2)
  expect(problems).toHaveTextContent('第 1 條規則缺少條件。')
  expect(screen.getByRole('button', { name: '回測' })).toBeDisabled()
})

test('策略有警告時顯示警告，但仍可回測', async () => {
  editor.result = { ok: true, strategy: STRATEGY, warnings: ['停損規則沒有排在第一條'] }

  render(<App />)

  expect(await screen.findByRole('list', { name: '策略的提醒' })).toHaveTextContent(
    '停損規則沒有排在第一條',
  )
  expect(screen.getByRole('button', { name: '回測' })).toBeEnabled()
})

test('回測失敗時顯示錯誤訊息', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('error', { status: 500 })))

  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: '回測' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('回測失敗')
})
