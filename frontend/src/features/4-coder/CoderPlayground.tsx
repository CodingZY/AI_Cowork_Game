import { useEffect } from 'react'
import { StageStrip } from './StageStrip'
import { FileTree } from './FileTree'
import { CodeEditor } from './CodeEditor'
import { TerminalLogs } from './TerminalLogs'
import { FeedbackDock } from './FeedbackDock'
import { useGameStore, useIsRealDevProject } from '@/store/useGameStore'

/** 页面四：代码增量生成与试玩工作区。
 * 真后端 project（id 数字）：轮询 dev state，各组件从 devState 派生（StageStrip/FileTree/FeedbackDock/TerminalLogs）。
 * 可试玩 URL 由左栏模块控制提供（外链），不再嵌 Web 试玩 iframe。
 * mock project：保留 mock 链路。 */
export function CoderPlayground() {
  const isReal = useIsRealDevProject()
  const ensureDevPoll = useGameStore((s) => s.ensureDevPoll)
  const stopDevPoll = useGameStore((s) => s.stopDevPoll)
  const loadDevGitTags = useGameStore((s) => s.loadDevGitTags)
  const loadDevSrcTree = useGameStore((s) => s.loadDevSrcTree)

  useEffect(() => {
    if (isReal) {
      ensureDevPoll()
      void loadDevGitTags()
      void loadDevSrcTree()
      return () => stopDevPoll()
    }
  }, [isReal, ensureDevPoll, stopDevPoll, loadDevGitTags, loadDevSrcTree])

  return (
    <div className="flex h-full min-h-0 flex-col">
      <StageStrip />
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto p-3 xl:grid-cols-[260px_1fr_380px] xl:grid-rows-1 xl:overflow-hidden">
        {/* 左：文件树 + 模块控制（含最新可试玩 URL） */}
        <FileTree />

        {/* 中：代码编辑器（拉满高度） */}
        <div className="min-h-[420px] xl:min-h-0">
          <CodeEditor />
        </div>

        {/* 右：终端/自检日志 + 反馈停靠 */}
        <div className="flex min-h-0 flex-col gap-3">
          <div className="min-h-[420px] flex-1 xl:min-h-0">
            <TerminalLogs />
          </div>
          <div className="shrink-0">
            <FeedbackDock />
          </div>
        </div>
      </div>
    </div>
  )
}
