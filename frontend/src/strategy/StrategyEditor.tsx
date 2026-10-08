import * as Blockly from 'blockly/core'
import * as ZhHant from 'blockly/msg/zh-hant'
import { useEffect, useRef } from 'react'
import { registerBlocks, TOOLBOX } from './blocks'
import { type ConversionResult, stateToStrategy, strategyToState } from './convert'
import type { Strategy } from './types'

type Props = {
  initialStrategy: Strategy
  onChange: (result: ConversionResult) => void
}

/** Blockly 策略編輯器（只支援桌機）。每次編輯後回報轉換後的策略 JSON 或錯誤。 */
export function StrategyEditor({ initialStrategy, onChange }: Props) {
  const container = useRef<HTMLDivElement>(null)
  // 初始策略只在掛載時載入一次；onChange 用 ref 保持最新，不必重建工作區
  const initial = useRef(initialStrategy)
  const latestOnChange = useRef(onChange)
  useEffect(() => {
    latestOnChange.current = onChange
  }, [onChange])

  useEffect(() => {
    if (!container.current) return
    Blockly.setLocale(ZhHant as unknown as { [key: string]: string })
    registerBlocks()
    const workspace = Blockly.inject(container.current, {
      toolbox: TOOLBOX,
      trashcan: true,
      // 圖示與游標由網站自己提供（public/blockly-media，複製自 blockly 套件），音效關閉；
      // 否則 Blockly 會從外部網站下載
      media: '/blockly-media/',
      sounds: false,
      zoom: { controls: true, wheel: false, startScale: 0.9 },
      move: { scrollbars: true, drag: true, wheel: true },
    })
    Blockly.serialization.workspaces.load(strategyToState(initial.current), workspace)

    const report = () =>
      latestOnChange.current(stateToStrategy(Blockly.serialization.workspaces.save(workspace)))
    report()
    const listener = (event: Blockly.Events.Abstract) => {
      if (!event.isUiEvent) report()
    }
    workspace.addChangeListener(listener)

    return () => {
      workspace.removeChangeListener(listener)
      workspace.dispose()
    }
  }, [])

  return <div ref={container} className="strategy-editor" aria-label="策略編輯器" />
}
