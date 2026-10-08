// Blockly 工作區狀態（Blockly 的序列化 JSON）與策略 JSON 的雙向轉換（ADR 0006）。
// 純函式，不依賴 DOM，方便測試。
//
// 「且／或」積木只有兩個輸入；轉成策略 JSON 時，同種類的巢狀群組會攤平成一層，
// 例如 A 且 (B 且 C) → all[A, B, C]。反方向則把多個條件接成右巢狀的兩兩一組。

import type * as Blockly from 'blockly/core'
import { CONDITION_BLOCKS, GROUP_BLOCK, ROOT_BLOCK, RULE_BLOCK } from './blocks'
import { type Condition, type Rule, STRATEGY_FORMAT_VERSION, type Strategy } from './types'

type BlockState = Blockly.serialization.blocks.State
export type WorkspaceState = { blocks?: { languageVersion: number; blocks: BlockState[] } }

export type ConversionResult =
  | { ok: true; strategy: Strategy; warnings: string[] }
  | { ok: false; errors: string[] }

const CONDITION_TYPE_BY_BLOCK = new Map(CONDITION_BLOCKS.map((b) => [b.type, b.conditionType]))
const BLOCK_BY_CONDITION_TYPE = new Map(CONDITION_BLOCKS.map((b) => [b.conditionType, b]))
const PERCENT_FIELDS = new Map(CONDITION_BLOCKS.map((b) => [b.type, new Set(b.percentFields)]))

const STOP_LOSS_NOT_FIRST = '停損規則沒有排在第一條：同一天其他規則成立時，停損可能不會執行。'

/** 去掉浮點誤差，例如 0.07 × 100 = 7.000000000000001。 */
function clean(value: number): number {
  return Math.round(value * 1e10) / 1e10
}

// --- 工作區 → 策略 JSON ---------------------------------------------------

export function stateToStrategy(state: WorkspaceState): ConversionResult {
  const root = state.blocks?.blocks.find((b) => b.type === ROOT_BLOCK)
  if (!root) return { ok: false, errors: ['找不到「策略」積木。'] }

  const errors: string[] = []
  const rules: Rule[] = []
  let block = root.inputs?.RULES?.block
  while (block) {
    const n = rules.length + 1
    const conditionBlock = block.inputs?.CONDITION?.block
    const condition = conditionBlock
      ? toCondition(conditionBlock, errors, n)
      : (errors.push(`第 ${n} 條規則缺少條件。`), null)
    rules.push({ action: block.fields?.ACTION as Rule['action'], condition: condition! })
    block = block.next?.block
  }
  if (rules.length === 0) errors.push('策略至少需要一條規則。')
  const entryRatios = parseRatios('進場比例', root.fields?.ENTRY_RATIOS, errors)
  const exitRatios = parseRatios('出場比例', root.fields?.EXIT_RATIOS, errors)
  if (errors.length > 0) return { ok: false, errors }

  const warnings: string[] = []
  const stopLossIndex = rules.findIndex((r) => r.action === 'stop_loss')
  if (stopLossIndex > 0) warnings.push(STOP_LOSS_NOT_FIRST)

  return {
    ok: true,
    strategy: {
      version: STRATEGY_FORMAT_VERSION,
      rules,
      entry_ratios: entryRatios!,
      exit_ratios: exitRatios!,
    },
    warnings,
  }
}

/** 「50/30/20」→ [0.5, 0.3, 0.2]；1 到 5 批、每批大於 0、合計 100%。 */
function parseRatios(name: string, text: unknown, errors: string[]): number[] | null {
  const parts = String(text ?? '')
    .split('/')
    .map((p) => p.trim())
  const percents = parts.map(Number)
  const valid =
    parts.length >= 1 &&
    parts.length <= 5 &&
    parts.every((p) => p !== '') &&
    percents.every((p) => Number.isFinite(p) && p > 0) &&
    Math.abs(percents.reduce((a, b) => a + b, 0) - 100) < 1e-6
  if (!valid) {
    errors.push(`${name}必須是 1 到 5 個以「/」分隔、大於 0、合計 100 的百分比，例如 50/30/20。`)
    return null
  }
  return percents.map((p) => clean(p / 100))
}

function formatRatios(ratios: number[]): string {
  return ratios.map((r) => clean(r * 100)).join('/')
}

function toCondition(block: BlockState, errors: string[], ruleNumber: number): Condition | null {
  if (block.type === GROUP_BLOCK) {
    const op = block.fields?.OP as 'all' | 'any'
    const parts = (['A', 'B'] as const).map((name) => block.inputs?.[name]?.block)
    if (parts.some((p) => !p)) {
      errors.push(`第 ${ruleNumber} 條規則的「${op === 'all' ? '且' : '或'}」積木缺少條件。`)
      return null
    }
    const conditions = parts.map((p) => toCondition(p!, errors, ruleNumber))
    if (conditions.some((c) => c === null)) return null
    // 攤平同種類的巢狀群組
    const flat = (conditions as Condition[]).flatMap((c) =>
      c.type === op ? (c as { conditions: Condition[] }).conditions : [c],
    )
    return { type: op, conditions: flat }
  }

  const conditionType = CONDITION_TYPE_BY_BLOCK.get(block.type)
  if (!conditionType) {
    errors.push(`第 ${ruleNumber} 條規則含有不認得的積木：${block.type}`)
    return null
  }
  const percent = PERCENT_FIELDS.get(block.type)!
  const fields = Object.fromEntries(
    Object.entries(block.fields ?? {}).map(([name, value]) => [
      name.toLowerCase(),
      percent.has(name) ? clean(Number(value) / 100) : value,
    ]),
  )
  return { type: conditionType, ...fields } as Condition
}

// --- 策略 JSON → 工作區 ---------------------------------------------------

export function strategyToState(strategy: Strategy): WorkspaceState {
  const rules = [...strategy.rules].reverse().reduce<BlockState | undefined>(
    (next, rule) => ({
      type: RULE_BLOCK,
      fields: { ACTION: rule.action },
      inputs: { CONDITION: { block: toBlock(rule.condition) } },
      ...(next && { next: { block: next } }),
    }),
    undefined,
  )
  return {
    blocks: {
      languageVersion: 0,
      blocks: [
        {
          type: ROOT_BLOCK,
          x: 20,
          y: 20,
          deletable: false,
          fields: {
            ENTRY_RATIOS: formatRatios(strategy.entry_ratios),
            EXIT_RATIOS: formatRatios(strategy.exit_ratios),
          },
          ...(rules && { inputs: { RULES: { block: rules } } }),
        },
      ],
    },
  }
}

function toBlock(condition: Condition): BlockState {
  if (condition.type === 'all' || condition.type === 'any') {
    const [first, ...rest] = condition.conditions
    if (rest.length === 0) return toBlock(first)
    return {
      type: GROUP_BLOCK,
      fields: { OP: condition.type },
      inputs: {
        A: { block: toBlock(first) },
        B: { block: toBlock({ type: condition.type, conditions: rest }) },
      },
    }
  }

  const definition = BLOCK_BY_CONDITION_TYPE.get(condition.type)
  if (!definition) throw new Error(`編輯器不支援的條件積木：${condition.type}`)
  const percent = new Set(definition.percentFields)
  const fields = Object.fromEntries(
    Object.entries(condition)
      .filter(([key]) => key !== 'type')
      .map(([key, value]) => {
        const name = key.toUpperCase()
        return [name, percent.has(name) ? clean((value as number) * 100) : value]
      }),
  )
  return { type: definition.type, fields }
}
