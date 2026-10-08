import { useState } from 'react'

type PerformanceReport = {
  initial_capital: number
  final_equity: number
  total_return: number
}

const INITIAL_CAPITAL = 1_000_000

function formatPercent(ratio: number): string {
  const sign = ratio > 0 ? '+' : ''
  return `${sign}${(ratio * 100).toFixed(2)}%`
}

export default function App() {
  const [report, setReport] = useState<PerformanceReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  async function runBacktest() {
    setRunning(true)
    setError(null)
    try {
      const response = await fetch('/api/backtests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ initial_capital: INITIAL_CAPITAL }),
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setReport((await response.json()) as PerformanceReport)
    } catch {
      setReport(null)
      setError('回測失敗，請稍後再試。')
    } finally {
      setRunning(false)
    }
  }

  return (
    <main>
      <h1>台股回測系統</h1>
      <p className="muted">
        示範策略：收盤價站上 20 日均線進場、跌破出場；行情為示範資料。
      </p>
      <button type="button" onClick={runBacktest} disabled={running}>
        回測
      </button>
      {error && <p role="alert">{error}</p>}
      {report && (
        <section aria-label="績效報告">
          <h2>總報酬</h2>
          <p className={report.total_return >= 0 ? 'up' : 'down'}>
            {formatPercent(report.total_return)}
          </p>
        </section>
      )}
    </main>
  )
}
