import { StageStrip } from './StageStrip'
import { FileTree } from './FileTree'
import { CodeEditor } from './CodeEditor'
import { TerminalLogs } from './TerminalLogs'
import { LivePreview } from './LivePreview'
import { FeedbackDock } from './FeedbackDock'

/** 页面四：代码增量生成与 Web 试玩工作区。 */
export function CoderPlayground() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <StageStrip />
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto p-3 xl:grid-cols-[260px_1fr_380px] xl:grid-rows-1 xl:overflow-hidden">
        {/* 左：文件树 + 模块控制 */}
        <FileTree />

        {/* 中：代码编辑器 + 终端日志 */}
        <div className="flex min-h-0 flex-col gap-3">
          <div className="min-h-[420px] flex-1 xl:min-h-0">
            <CodeEditor />
          </div>
          <div className="h-[260px] shrink-0">
            <TerminalLogs />
          </div>
        </div>

        {/* 右：试玩预览 + 反馈停靠 */}
        <div className="flex min-h-0 flex-col gap-3">
          <div className="min-h-[420px] flex-1 xl:min-h-0">
            <LivePreview />
          </div>
          <div className="shrink-0">
            <FeedbackDock />
          </div>
        </div>
      </div>
    </div>
  )
}
