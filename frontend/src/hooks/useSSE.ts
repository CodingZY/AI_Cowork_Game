import { useEffect, useRef } from 'react'
import { connectSSE, type CoworkEvent } from '@/api/backend'

export function useSSE(projectId: number | null, onEvent: (e: CoworkEvent) => void) {
  const cbRef = useRef(onEvent)
  cbRef.current = onEvent
  useEffect(() => {
    if (projectId == null) return
    const close = connectSSE(projectId, (e) => cbRef.current(e))
    return close
  }, [projectId])
}
