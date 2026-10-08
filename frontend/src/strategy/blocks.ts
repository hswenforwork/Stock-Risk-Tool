// Blockly 積木定義。條件積木的欄位名稱（大寫）對應策略 JSON 的鍵（小寫），
// 例如 PERIOD ↔ period，讓 convert.ts 可以通用地轉換。

import * as Blockly from 'blockly/core'

export const ROOT_BLOCK = 'strategy_root'
export const RULE_BLOCK = 'strategy_rule'
export const GROUP_BLOCK = 'condition_group'

const CONDITION = 'Condition'
const RULE = 'Rule'

const COLOURS = {
  strategy: 210,
  logic: 290,
  trend: 160,
  oscillator: 20,
  volume: 60,
}

type Arg = Record<string, unknown> & { type: string; name?: string }

type BlockDefinition = {
  type: string
  args0?: Arg[]
  [key: string]: unknown
}

function num(name: string, value: number, min: number, max?: number, precision = 1): Arg {
  return { type: 'field_number', name, value, min, max, precision }
}

function dropdown(name: string, options: [string, string][]): Arg {
  return { type: 'field_dropdown', name, options }
}

const ABOVE_BELOW = dropdown('OP', [
  ['高於', 'above'],
  ['低於', 'below'],
])
const GOLDEN_DEATH = dropdown('OP', [
  ['黃金交叉', 'golden'],
  ['死亡交叉', 'death'],
])

function condition(
  type: string,
  conditionType: string,
  message0: string,
  args0: Arg[],
  colour: number,
  tooltip: string,
): BlockDefinition & { conditionType: string } {
  return { type, conditionType, message0, args0, output: CONDITION, colour, tooltip }
}

/** 條件積木：積木類型 → 策略 JSON 的條件類型。 */
export const CONDITION_BLOCKS = [
  condition(
    'cond_close_vs_sma',
    'close_vs_sma',
    '收盤價 %1 %2 日均線',
    [
      dropdown('OP', [
        ['站上', 'above'],
        ['跌破', 'below'],
      ]),
      num('PERIOD', 20, 1),
    ],
    COLOURS.trend,
    '收盤價高於或低於 N 日均線',
  ),
  condition(
    'cond_sma_cross',
    'sma_cross',
    '%1 日均線 %2 %3 日均線',
    [num('FAST', 5, 1), GOLDEN_DEATH, num('SLOW', 20, 2)],
    COLOURS.trend,
    '短天期均線向上（黃金交叉）或向下（死亡交叉）穿越長天期均線',
  ),
  condition(
    'cond_close_vs_value',
    'close_vs_value',
    '收盤價 %1 %2 元',
    [ABOVE_BELOW, num('VALUE', 100, 0, undefined, 0.01)],
    COLOURS.trend,
    '收盤價高於或低於固定價格',
  ),
  condition(
    'cond_rsi',
    'rsi',
    '%1 日 RSI %2 %3',
    [num('PERIOD', 14, 2), ABOVE_BELOW, num('VALUE', 70, 0, 100, 0.1)],
    COLOURS.oscillator,
    'RSI（Wilder 平滑）高於或低於某數值',
  ),
  condition(
    'cond_macd_cross',
    'macd_cross',
    'MACD（快 %1、慢 %2、訊號 %3）%4',
    [num('FAST', 12, 1), num('SLOW', 26, 2), num('SIGNAL', 9, 1), GOLDEN_DEATH],
    COLOURS.oscillator,
    'MACD 的 DIF 向上或向下穿越訊號線',
  ),
  condition(
    'cond_kd_cross',
    'kd_cross',
    '%1 日 KD %2',
    [num('PERIOD', 9, 2), GOLDEN_DEATH],
    COLOURS.oscillator,
    'K 值向上或向下穿越 D 值',
  ),
  condition(
    'cond_kd_level',
    'kd_level',
    '%1 日 %2 值 %3 %4',
    [
      num('PERIOD', 9, 2),
      dropdown('LINE', [
        ['K', 'k'],
        ['D', 'd'],
      ]),
      ABOVE_BELOW,
      num('VALUE', 80, 0, 100, 0.1),
    ],
    COLOURS.oscillator,
    'K 值或 D 值高於或低於某數值',
  ),
  condition(
    'cond_bollinger',
    'bollinger',
    '收盤價 %1（%2 日、%3 倍標準差）',
    [
      dropdown('OP', [
        ['突破布林上軌', 'above_upper'],
        ['跌破布林下軌', 'below_lower'],
      ]),
      num('PERIOD', 20, 2),
      num('STD', 2, 0.1, undefined, 0.1),
    ],
    COLOURS.oscillator,
    '收盤價突破布林通道上軌或跌破下軌',
  ),
  condition(
    'cond_volume_vs_avg',
    'volume_vs_avg',
    '成交量 %1 前 %2 日均量的 %3 倍',
    [
      dropdown('OP', [
        ['大於', 'above'],
        ['小於', 'below'],
      ]),
      num('PERIOD', 5, 1),
      num('MULTIPLE', 1.5, 0.1, undefined, 0.1),
    ],
    COLOURS.volume,
    '當天成交量與前 N 日（不含當天）平均成交量比較',
  ),
]

export const ACTION_OPTIONS: [string, string][] = [
  ['進場', 'entry'],
  ['出場', 'exit'],
]

const STRUCTURE_BLOCKS: BlockDefinition[] = [
  {
    type: ROOT_BLOCK,
    message0: '策略（由上往下比對，每天只執行第一條成立的規則）',
    message1: '%1',
    args1: [{ type: 'input_statement', name: 'RULES', check: RULE }],
    colour: COLOURS.strategy,
    tooltip: '把規則接在這裡；越上面的規則優先順序越高',
  },
  {
    type: RULE_BLOCK,
    message0: '%1 當 %2',
    args0: [
      dropdown('ACTION', ACTION_OPTIONS),
      { type: 'input_value', name: 'CONDITION', check: CONDITION },
    ],
    previousStatement: RULE,
    nextStatement: RULE,
    colour: COLOURS.strategy,
    tooltip: '規則：條件成立時，下一個交易日開盤執行動作',
  },
  {
    type: GROUP_BLOCK,
    message0: '%1',
    args0: [{ type: 'input_value', name: 'A', check: CONDITION }],
    message1: '%1 %2',
    args1: [
      dropdown('OP', [
        ['且', 'all'],
        ['或', 'any'],
      ]),
      { type: 'input_value', name: 'B', check: CONDITION },
    ],
    output: CONDITION,
    colour: COLOURS.logic,
    tooltip: '且：兩個條件都成立；或：任一個條件成立。可以互相巢狀組合。',
  },
]

let registered = false

/** 註冊所有積木（重複呼叫沒有副作用）。 */
export function registerBlocks(): void {
  if (registered) return
  Blockly.common.defineBlocksWithJsonArray([...STRUCTURE_BLOCKS, ...CONDITION_BLOCKS])
  registered = true
}

export const TOOLBOX = {
  kind: 'categoryToolbox',
  contents: [
    {
      kind: 'category',
      name: '規則',
      colour: String(COLOURS.strategy),
      contents: [{ kind: 'block', type: RULE_BLOCK }],
    },
    {
      kind: 'category',
      name: '且／或',
      colour: String(COLOURS.logic),
      contents: [{ kind: 'block', type: GROUP_BLOCK }],
    },
    {
      kind: 'category',
      name: '均線與價格',
      colour: String(COLOURS.trend),
      contents: ['cond_close_vs_sma', 'cond_sma_cross', 'cond_close_vs_value'].map((type) => ({
        kind: 'block',
        type,
      })),
    },
    {
      kind: 'category',
      name: '技術指標',
      colour: String(COLOURS.oscillator),
      contents: [
        'cond_rsi',
        'cond_macd_cross',
        'cond_kd_cross',
        'cond_kd_level',
        'cond_bollinger',
      ].map((type) => ({ kind: 'block', type })),
    },
    {
      kind: 'category',
      name: '成交量',
      colour: String(COLOURS.volume),
      contents: [{ kind: 'block', type: 'cond_volume_vs_avg' }],
    },
  ],
}
