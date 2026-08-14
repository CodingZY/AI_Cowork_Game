import { useCallback } from 'react'
import { useGameStore, useCurrentGame } from '@/store/useGameStore'
import type { EngineStage, WSMessage } from '@/types'

/**
 * 模拟 Agent WebSocket（前端设计文档.md §4.2）。
 * 真实环境连接 `ws://host/api/ws/{run_id}`；此处用 store 模拟，
 * `post` 按当前阶段路由到对应的 store 动作，`status` 即连接/Agent 状态。
 */
export function useAgentWebSocket(runId: string | null) {
  const connected = !!runId
  const status = useGameStore((s) => s.agentStatus)
  const game = useCurrentGame()

  const post = useCallback(
    (text: string) => {
      if (!text.trim()) return
      const stage: EngineStage | undefined = game?.currentStage
      const s = useGameStore.getState()
      if (stage === 'STAGE_1_BRAINSTORM') s.sendBrainstormText(text)
      // 其余阶段由各自页面用专用动作（copilot / coder 反馈）处理
    },
    [game?.currentStage],
  )

  // 预留：真实 WS 时在此 onMessage 派发 WSMessage 到 store
  const dispatch = useCallback((_msg: WSMessage) => {
    /* no-op in mock */
  }, [])

  return { connected, status, post, dispatch }
}
