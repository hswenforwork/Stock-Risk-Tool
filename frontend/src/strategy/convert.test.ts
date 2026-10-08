import * as Blockly from 'blockly/core'
import { beforeAll, describe, expect, test } from 'vitest'
import { registerBlocks } from './blocks'
import { stateToStrategy, strategyToState, type WorkspaceState } from './convert'
import { DEFAULT_STRATEGY } from './defaults'
import type { Condition, Strategy } from './types'

function strategyWith(...conditions: [Strategy['rules'][number]['action'], Condition][]): Strategy {
  return {
    version: 1,
    entry_ratios: [1],
    exit_ratios: [1],
    rules: conditions.map(([action, condition]) => ({ action, condition })),
  }
}

/** 每一種編輯器支援的條件積木各一個。 */
const EVERY_CONDITION: Condition[] = [
  { type: 'close_vs_sma', op: 'above', period: 20 },
  { type: 'sma_cross', op: 'golden', fast: 5, slow: 20 },
  { type: 'close_vs_value', op: 'below', value: 98.5 },
  { type: 'rsi', op: 'below', period: 14, value: 30 },
  { type: 'macd_cross', op: 'death', fast: 12, slow: 26, signal: 9 },
  { type: 'kd_cross', op: 'golden', period: 9 },
  { type: 'kd_level', line: 'd', op: 'above', value: 80, period: 9 },
  { type: 'bollinger', op: 'below_lower', period: 20, std: 2 },
  { type: 'volume_vs_avg', op: 'above', period: 5, multiple: 1.5 },
]

const NESTED = strategyWith(
  [
    'entry',
    {
      type: 'any',
      conditions: [
        {
          type: 'all',
          conditions: [
            { type: 'sma_cross', op: 'golden', fast: 5, slow: 20 },
            { type: 'volume_vs_avg', op: 'above', period: 5, multiple: 2 },
            { type: 'rsi', op: 'below', period: 14, value: 70 },
          ],
        },
        { type: 'bollinger', op: 'below_lower', period: 20, std: 2 },
      ],
    },
  ],
  ['exit', { type: 'sma_cross', op: 'death', fast: 5, slow: 20 }],
)

/** 載入一個不顯示畫面的 Blockly 工作區再存回來，確認積木定義與欄位名稱對得上。 */
function throughBlockly(state: WorkspaceState): WorkspaceState {
  const workspace = new Blockly.Workspace()
  try {
    Blockly.serialization.workspaces.load(state, workspace)
    return Blockly.serialization.workspaces.save(workspace) as WorkspaceState
  } finally {
    workspace.dispose()
  }
}

beforeAll(() => {
  registerBlocks()
})

describe('策略 JSON → 工作區 → 策略 JSON', () => {
  test.each(EVERY_CONDITION.map((c) => [c.type, c] as const))('%s 轉換前後不變', (_, condition) => {
    const strategy = strategyWith(['entry', condition])

    expect(stateToStrategy(strategyToState(strategy))).toEqual({ ok: true, strategy, warnings: [] })
  })

  test('任意巢狀的且／或轉換前後不變', () => {
    expect(stateToStrategy(strategyToState(NESTED))).toEqual({ ok: true, strategy: NESTED, warnings: [] })
  })

  test('規則順序保持不變', () => {
    const strategy = strategyWith(
      ['exit', EVERY_CONDITION[0]],
      ['entry', EVERY_CONDITION[1]],
      ['exit', EVERY_CONDITION[2]],
    )

    expect(stateToStrategy(strategyToState(strategy))).toEqual({ ok: true, strategy, warnings: [] })
  })

  test('經過真正的 Blockly 工作區載入與儲存後仍然不變', () => {
    const strategy: Strategy = {
      ...NESTED,
      rules: [...EVERY_CONDITION.map((condition) => ({ action: 'entry' as const, condition })), ...NESTED.rules],
    }

    expect(stateToStrategy(throughBlockly(strategyToState(strategy)))).toEqual({
      ok: true,
      strategy,
      warnings: [],
    })
  })

  test('預設策略可以載入編輯器', () => {
    expect(stateToStrategy(throughBlockly(strategyToState(DEFAULT_STRATEGY)))).toEqual({
      ok: true,
      strategy: DEFAULT_STRATEGY,
      warnings: [],
    })
  })
})

describe('攤平與正規化', () => {
  test('同種類的巢狀群組攤平成一層', () => {
    const a: Condition = { type: 'rsi', op: 'below', period: 14, value: 30 }
    const b: Condition = { type: 'kd_cross', op: 'golden', period: 9 }
    const c: Condition = { type: 'close_vs_sma', op: 'above', period: 60 }
    const nested = strategyWith([
      'entry',
      { type: 'all', conditions: [a, { type: 'all', conditions: [b, c] }] },
    ])

    const result = stateToStrategy(strategyToState(nested))

    expect(result.ok && result.strategy.rules[0].condition).toEqual({
      type: 'all',
      conditions: [a, b, c],
    })
  })

  test('只有一個條件的群組直接變成該條件', () => {
    const a: Condition = { type: 'rsi', op: 'below', period: 14, value: 30 }

    const result = stateToStrategy(
      strategyToState(strategyWith(['entry', { type: 'any', conditions: [a] }])),
    )

    expect(result.ok && result.strategy.rules[0].condition).toEqual(a)
  })
})

describe('不完整的策略', () => {
  test('沒有策略積木', () => {
    expect(stateToStrategy({ blocks: { languageVersion: 0, blocks: [] } })).toEqual({
      ok: false,
      errors: ['找不到「策略」積木。'],
    })
  })

  test('沒有任何規則', () => {
    const state = strategyToState({ ...NESTED, rules: [] })

    expect(stateToStrategy(state)).toEqual({ ok: false, errors: ['策略至少需要一條規則。'] })
  })

  test('規則缺少條件、且／或缺少其中一邊', () => {
    const state = strategyToState(NESTED)
    const root = state.blocks!.blocks[0]
    const firstRule = root.inputs!.RULES.block!
    const group = firstRule.inputs!.CONDITION.block!
    delete group.inputs!.B
    const secondRule = firstRule.next!.block!
    delete secondRule.inputs!.CONDITION

    expect(stateToStrategy(state)).toEqual({
      ok: false,
      errors: ['第 1 條規則的「或」積木缺少條件。', '第 2 條規則缺少條件。'],
    })
  })

  test('工作區上沒接到策略積木的零散積木會被忽略', () => {
    const state = strategyToState(NESTED)
    state.blocks!.blocks.push({ type: 'cond_rsi', fields: { PERIOD: 14, OP: 'above', VALUE: 70 } })

    expect(stateToStrategy(state)).toEqual({ ok: true, strategy: NESTED, warnings: [] })
  })
})

describe('加減碼、停損停利與分批比例（#11）', () => {
  const POSITION_CONDITIONS: Condition[] = [
    { type: 'price_vs_last_buy', op: 'up', pct: 0.05 },
    { type: 'price_vs_last_buy', op: 'down', pct: 0.1 },
    { type: 'price_vs_last_sell', op: 'up', pct: 0.03 },
    { type: 'price_vs_last_sell', op: 'down', pct: 0.025 },
    { type: 'pnl_vs_avg_cost', op: 'gain', pct: 0.2 },
    { type: 'pnl_vs_avg_cost', op: 'loss', pct: 0.08 },
  ]

  const FULL: Strategy = {
    version: 1,
    entry_ratios: [0.5, 0.3, 0.2],
    exit_ratios: [0.6, 0.4],
    rules: [
      { action: 'stop_loss', condition: { type: 'pnl_vs_avg_cost', op: 'loss', pct: 0.08 } },
      { action: 'take_profit', condition: { type: 'pnl_vs_avg_cost', op: 'gain', pct: 0.2 } },
      { action: 'exit', condition: { type: 'sma_cross', op: 'death', fast: 5, slow: 20 } },
      { action: 'reduce', condition: { type: 'price_vs_last_sell', op: 'down', pct: 0.03 } },
      { action: 'add', condition: { type: 'price_vs_last_buy', op: 'up', pct: 0.05 } },
      { action: 'entry', condition: { type: 'sma_cross', op: 'golden', fast: 5, slow: 20 } },
    ],
  }

  test.each(POSITION_CONDITIONS.map((c) => [`${c.type} ${'op' in c ? c.op : ''}`, c] as const))(
    '%s 轉換前後不變（積木上以百分比顯示）',
    (_, condition) => {
      const strategy = strategyWith(['add', condition])

      expect(stateToStrategy(throughBlockly(strategyToState(strategy)))).toEqual({
        ok: true,
        strategy,
        warnings: [],
      })
    },
  )

  test('百分比顯示在積木上', () => {
    const state = strategyToState(strategyWith(['add', POSITION_CONDITIONS[0]]))
    const condition = state.blocks!.blocks[0].inputs!.RULES.block!.inputs!.CONDITION.block!

    expect(condition.fields).toEqual({ OP: 'up', PCT: 5 })
  })

  test('六種動作、進場比例與出場比例轉換前後不變', () => {
    expect(stateToStrategy(throughBlockly(strategyToState(FULL)))).toEqual({
      ok: true,
      strategy: FULL,
      warnings: [],
    })
  })

  test('比例在策略積木上以「/」分隔的百分比顯示', () => {
    const root = strategyToState(FULL).blocks!.blocks[0]

    expect(root.fields).toEqual({ ENTRY_RATIOS: '50/30/20', EXIT_RATIOS: '60/40' })
  })

  test.each([
    ['50/30', '進場比例'],
    ['50/abc/50', '進場比例'],
    ['100/0', '進場比例'],
    ['', '進場比例'],
    ['20/20/20/20/10/10', '進場比例'],
  ])('進場比例「%s」不合法', (text, name) => {
    const state = strategyToState(FULL)
    state.blocks!.blocks[0].fields!.ENTRY_RATIOS = text

    const result = stateToStrategy(state)

    expect(result.ok).toBe(false)
    expect(!result.ok && result.errors[0]).toContain(name)
  })

  test('比例允許空白與小數', () => {
    const state = strategyToState(FULL)
    state.blocks!.blocks[0].fields!.EXIT_RATIOS = ' 33.4 / 33.3 / 33.3 '

    const result = stateToStrategy(state)

    expect(result.ok && result.strategy.exit_ratios).toEqual([0.334, 0.333, 0.333])
  })

  test('停損規則沒有排在第一條時提出警告，但仍可回測', () => {
    const strategy: Strategy = { ...FULL, rules: [FULL.rules[5], ...FULL.rules.slice(0, 5)] }

    const result = stateToStrategy(strategyToState(strategy))

    expect(result).toEqual({
      ok: true,
      strategy,
      warnings: ['停損規則沒有排在第一條：同一天其他規則成立時，停損可能不會執行。'],
    })
  })

  test('沒有停損規則時不提出警告', () => {
    const result = stateToStrategy(strategyToState(NESTED))

    expect(result.ok && result.warnings).toEqual([])
  })
})
