import { lazy, Suspense, useCallback, useState } from 'react'
import {
  BacktestError,
  EARLIEST_START_DATE,
  type Lot,
  type PerformanceReport,
  runBacktest,
} from './api'
import type { ConversionResult } from './strategy/convert'
import { DEFAULT_STRATEGY } from './strategy/defaults'
import { TradeTable } from './TradeTable'

const INITIAL_CAPITAL = 1_000_000

// Blockly 很大，延遲載入，不拖慢其他頁面
const StrategyEditor = lazy(() =>
  import('./strategy/StrategyEditor').then((m) => ({ default: m.StrategyEditor })),
)

function formatPercent(ratio: number): string {
  const sign = ratio > 0 ? '+' : ''
  return `${sign}${(ratio * 100).toFixed(2)}%`
}

export default function App() {
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [lot, setLot] = useState<Lot>('odd')
  const [report, setReport] = useState<PerformanceReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)
  const [edited, setEdited] = useState<ConversionResult>({
    ok: true,
    strategy: DEFAULT_STRATEGY,
    warnings: [],
  })
  const handleStrategyChange = useCallback((result: ConversionResult) => setEdited(result), [])

  // ISO 日期字串可以直接比較先後
  const startTooEarly = startDate !== '' && startDate < EARLIEST_START_DATE

  async function handleRun() {
    if (!edited.ok) return
    setRunning(true)
    setError(null)
    try {
      setReport(
        await runBacktest({
          initial_capital: INITIAL_CAPITAL,
          lot,
          strategy: edited.strategy,
          ...(startDate && { start_date: startDate }),
          ...(endDate && { end_date: endDate }),
        }),
      )
    } catch (e) {
      setReport(null)
      setError(e instanceof BacktestError ? e.message : '回測失敗，請稍後再試。')
    } finally {
      setRunning(false)
    }
  }

  return (
    <main>
      <h1>台股回測系統</h1>
      <p className="muted">
        從左側拖拉積木組合策略，接到「策略」積木底下；在「策略」積木上設定進場與出場的分批比例。
        行情為示範資料。
      </p>

      <Suspense fallback={<div className="strategy-editor muted">載入策略編輯器中…</div>}>
        <StrategyEditor initialStrategy={DEFAULT_STRATEGY} onChange={handleStrategyChange} />
      </Suspense>
      {!edited.ok && (
        <ul aria-label="策略的問題" className="problems">
          {edited.errors.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}
      {edited.ok && edited.warnings.length > 0 && (
        <ul aria-label="策略的提醒" className="warnings">
          {edited.warnings.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}

      <form
        className="settings"
        onSubmit={(e) => {
          e.preventDefault()
          void handleRun()
        }}
      >
        <label>
          起始日
          <input
            type="date"
            min={EARLIEST_START_DATE}
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
        </label>
        <label>
          結束日
          <input
            type="date"
            min={startDate || EARLIEST_START_DATE}
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </label>
        <label>
          成交單位
          <select value={lot} onChange={(e) => setLot(e.target.value as Lot)}>
            <option value="odd">零股</option>
            <option value="board">整張</option>
          </select>
        </label>
        <button type="submit" disabled={running || startTooEarly || !edited.ok}>
          回測
        </button>
      </form>
      <p className="muted hint">
        回測最早從 {EARLIEST_START_DATE} 開始：盤中零股交易在這天才開放。訊號在收盤後判斷，
        於下一個交易日開盤成交。
      </p>

      {startTooEarly && (
        <p role="alert">
          盤中零股交易 {EARLIEST_START_DATE} 才開放，起始日不能早於這天。
        </p>
      )}
      {error && <p role="alert">{error}</p>}

      {report && (
        <section aria-label="績效報告">
          <h2>總報酬</h2>
          <p className={report.total_return >= 0 ? 'up' : 'down'}>
            {formatPercent(report.total_return)}
          </p>
          <h2>交易明細</h2>
          <TradeTable trades={report.trades} />
        </section>
      )}
    </main>
  )
}
