import { Routes, Route, Navigate } from 'react-router-dom'
import { AppShell } from '@/components/shared/AppShell'
import { BrainstormHub } from '@/features/1-brainstorm/BrainstormHub'
import { DesignSpecPage } from '@/features/2-design/DesignSpecPage'
import { AssetStudio } from '@/features/3-assets/AssetStudio'
import { CoderPlayground } from '@/features/4-coder/CoderPlayground'
import { ReleasePage } from '@/features/5-versions/ReleasePage'

export default function App() {
  return (
    <AppShell>
      <Routes>
        <Route path="/brainstorm" element={<BrainstormHub />} />
        <Route path="/design" element={<DesignSpecPage />} />
        <Route path="/assets" element={<AssetStudio />} />
        <Route path="/coder" element={<CoderPlayground />} />
        <Route path="/release" element={<ReleasePage />} />
        <Route path="*" element={<Navigate to="/brainstorm" replace />} />
      </Routes>
    </AppShell>
  )
}
