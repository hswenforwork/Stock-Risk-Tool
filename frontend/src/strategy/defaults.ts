import type { Strategy } from './types'

/**
 * 編輯器第一次打開時的策略：
 * 虧損 8% 停損；5 日均線死亡交叉 20 日均線出場，之後比上一批賣出價再跌 3% 減碼；
 * 比上一批買進價上漲 5% 加碼；5 日均線黃金交叉 20 日均線進場。
 * 進場分 50/30/20 三層，出場分 50/50 兩批。
 */
export const DEFAULT_STRATEGY: Strategy = {
  version: 1,
  entry_ratios: [0.5, 0.3, 0.2],
  exit_ratios: [0.5, 0.5],
  rules: [
    { action: 'stop_loss', condition: { type: 'pnl_vs_avg_cost', op: 'loss', pct: 0.08 } },
    { action: 'exit', condition: { type: 'sma_cross', op: 'death', fast: 5, slow: 20 } },
    { action: 'reduce', condition: { type: 'price_vs_last_sell', op: 'down', pct: 0.03 } },
    { action: 'add', condition: { type: 'price_vs_last_buy', op: 'up', pct: 0.05 } },
    { action: 'entry', condition: { type: 'sma_cross', op: 'golden', fast: 5, slow: 20 } },
  ],
}
