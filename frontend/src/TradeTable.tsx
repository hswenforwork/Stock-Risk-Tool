import type { Action, Trade } from './api'

const ACTION_LABELS: Record<Action, string> = {
  entry: '進場',
  add: '加碼',
  reduce: '減碼',
  exit: '出場',
  stop_loss: '停損',
  take_profit: '停利',
}

const BUY_ACTIONS: ReadonlySet<Action> = new Set(['entry', 'add'])

function batchLabel(t: Trade): string {
  return BUY_ACTIONS.has(t.action) ? `第 ${t.batch} 層` : `第 ${t.batch} 批`
}

const integer = new Intl.NumberFormat('zh-TW', { maximumFractionDigits: 0 })
const price = new Intl.NumberFormat('zh-TW', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export function TradeTable({ trades }: { trades: Trade[] }) {
  if (trades.length === 0) return <p className="muted">回測期間沒有任何成交。</p>

  return (
    <div className="table-scroll">
      <table aria-label="交易明細">
        <thead>
          <tr>
            <th>日期</th>
            <th>動作</th>
            <th>層／批</th>
            <th className="num">股數</th>
            <th className="num">成交價</th>
            <th className="num">手續費</th>
            <th className="num">證交稅</th>
            <th>備註</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={`${t.date}-${t.action}-${t.batch}`}>
              <td>{t.date}</td>
              <td>{ACTION_LABELS[t.action]}</td>
              <td>{batchLabel(t)}</td>
              <td className="num">{integer.format(t.shares)}</td>
              <td className="num">{price.format(t.price)}</td>
              <td className="num">{integer.format(t.fee)}</td>
              <td className="num">{integer.format(t.tax)}</td>
              <td>{t.delayed ? '停牌延後' : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
