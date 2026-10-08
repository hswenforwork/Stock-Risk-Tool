// 策略 JSON（ADR 0006），與後端 backend/src/backtest/models.py 對應。

export type Action = 'entry' | 'add' | 'reduce' | 'exit' | 'stop_loss' | 'take_profit'

export type Condition =
  | { type: 'close_vs_sma'; op: 'above' | 'below'; period: number }
  | { type: 'close_vs_value'; op: 'above' | 'below'; value: number }
  | { type: 'sma_cross'; op: 'golden' | 'death'; fast: number; slow: number }
  | { type: 'rsi'; op: 'above' | 'below'; period: number; value: number }
  | { type: 'macd_cross'; op: 'golden' | 'death'; fast: number; slow: number; signal: number }
  | { type: 'kd_cross'; op: 'golden' | 'death'; period: number }
  | { type: 'kd_level'; line: 'k' | 'd'; op: 'above' | 'below'; value: number; period: number }
  | { type: 'bollinger'; op: 'above_upper' | 'below_lower'; period: number; std: number }
  | { type: 'volume_vs_avg'; op: 'above' | 'below'; period: number; multiple: number }
  | { type: 'price_vs_last_buy'; op: 'up' | 'down'; pct: number }
  | { type: 'price_vs_last_sell'; op: 'up' | 'down'; pct: number }
  | { type: 'pnl_vs_avg_cost'; op: 'gain' | 'loss'; pct: number }
  | { type: 'all' | 'any'; conditions: Condition[] }

export type Rule = { action: Action; condition: Condition }

export type Strategy = {
  version: 1
  rules: Rule[]
  entry_ratios: number[]
  exit_ratios: number[]
}

export const STRATEGY_FORMAT_VERSION = 1
