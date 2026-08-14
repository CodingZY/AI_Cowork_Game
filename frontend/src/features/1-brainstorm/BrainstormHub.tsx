import { ArchivedGameGrid } from './ArchivedGameGrid'
import { SuperpowerChat } from './SuperpowerChat'

/** 页面一：头脑风暴与项目孵化中心。 */
export function BrainstormHub() {
  return (
    <div className="grid h-full min-h-0 grid-cols-1 gap-3 p-3 lg:grid-cols-[340px_1fr]">
      <ArchivedGameGrid />
      <SuperpowerChat />
    </div>
  )
}
