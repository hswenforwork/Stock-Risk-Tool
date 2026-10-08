// 與後端 /api/backtests 對應的型別與呼叫。

export const EARLIEST_START_DATE = '2020-10-26'

export type Lot = 'odd' | 'board'

export type BacktestSettings = {
  initial_capital: number
  start_date?: string
  end_date?: string
  lot: Lot
}

export type Trade = {
  date: string
  action: 'entry' | 'exit'
  shares: number
  price: number
  fee: number
  tax: number
  delayed: boolean
}

export type PerformanceReport = {
  initial_capital: number
  final_equity: number
  total_return: number
  trades: Trade[]
}

export class BacktestError extends Error {}

type ValidationError = { detail?: { msg?: string }[] }

export async function runBacktest(settings: BacktestSettings): Promise<PerformanceReport> {
  const response = await fetch('/api/backtests', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (response.status === 422) {
    const body = (await response.json().catch(() => ({}))) as ValidationError
    const reason = body.detail?.[0]?.msg?.replace(/^Value error, /, '')
    throw new BacktestError(reason ?? '回測設定不正確。')
  }
  if (!response.ok) throw new BacktestError('回測失敗，請稍後再試。')
  return (await response.json()) as PerformanceReport
}
