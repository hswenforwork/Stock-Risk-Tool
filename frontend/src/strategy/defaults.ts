import type { Strategy } from './types'

/** 編輯器第一次打開時的策略：5 日均線黃金交叉 20 日均線進場、死亡交叉出場。 */
export const DEFAULT_STRATEGY: Strategy = {
  version: 1,
  entry_ratios: [1],
  exit_ratios: [1],
  rules: [
    { action: 'entry', condition: { type: 'sma_cross', op: 'golden', fast: 5, slow: 20 } },
    { action: 'exit', condition: { type: 'sma_cross', op: 'death', fast: 5, slow: 20 } },
  ],
}
