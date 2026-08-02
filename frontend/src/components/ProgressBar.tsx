const STAGES = [
  { id: 'S1_design', label: '设计' },
  { id: 'S2_art_plan', label: '美术清单' },
  { id: 'S3_art_gen', label: '素材生成' },
  { id: 'S4_coding', label: '代码' },
  { id: 'S5_done', label: '完成' },
]

export function ProgressBar({ current }: { current: string }) {
  return (
    <div style={{ display: 'flex', gap: 8, padding: 8 }}>
      {STAGES.map(s => (
        <div key={s.id} className={s.id === current ? 'active' : ''} style={{ padding: '4px 10px', border: '1px solid #ccc', borderRadius: 4, background: s.id === current ? '#def' : '#fff' }}>
          {s.label}
        </div>
      ))}
    </div>
  )
}
