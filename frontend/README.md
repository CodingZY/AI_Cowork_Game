# AI Game Engine Studio · 前端

> 依据根目录 `前端设计文档.md` 重建。**暂不对接后端**，所有数据与 Agent 流式 / 素材生成 / 无头自检均由本地 mock 层模拟。

## 启动

```bash
cd frontend
npm install        # cache 已指向 D 盘，不写 C 盘
npm run dev        # http://localhost:5173
npm run typecheck  # tsc --noEmit
npm run build      # tsc --noEmit && vite build
```

> Monaco 编辑器通过 `@monaco-editor/react` 默认从 CDN 加载核心，首次使用需联网。

## 技术栈

- React 18 + Vite + TypeScript
- Tailwind CSS v3（暗黑 token）+ Shadcn 风格组件（基于 Radix UI 原语）
- Zustand（全局状态）· react-router-dom v6（路由）· lucide-react（图标）
- @monaco-editor/react（代码 / Markdown 编辑）· react-markdown + remark-gfm（渲染）

## 视觉

Dark Modern Studio Style：
`canvas #0F172A` · `surface #1E293B` · `accent emerald #10B981` · `accent-2 cyan #06B6D4` · `danger #EF4444` · 文字 `#F8FAFC` / `#94A3B8`。token 见 `tailwind.config.js`。

## 目录结构

```
src/
├── components/
│   ├── ui/        # Button/Card/Tabs/Dialog/Sheet/Badge/... 基础组件
│   └── shared/    # Header/StageStepper/GameSwitcher/AppShell/MarkdownView
├── features/
│   ├── 1-brainstorm/   # 头脑风暴 Hub
│   ├── 2-design/       # 需求 / 美术素材协同编辑
│   ├── 3-assets/       # 素材生成与抠图工坊
│   ├── 4-coder/        # 代码迭代与试玩工作区
│   └── 5-versions/     # Git 版本管理 + 发布
├── store/useGameStore.ts   # Zustand：状态机 + 模拟流
├── services/
│   ├── mockData.ts     # 静态 mock（游戏 / 文档 / 素材 / 文件树 / 模块 / 版本 / 对话）
│   └── mockApi.ts      # 模拟 API（流式 / 生成 / 抠图 / 无头自检 / 存版本）
├── hooks/useAgentWebSocket.ts  # 模拟 Agent WebSocket（§4.2 消息协议）
└── types.ts           # 阶段状态机 + 各领域类型
```

## 5 阶段状态机

`STAGE_1_BRAINSTORM → STAGE_2_DESIGN_DOC → STAGE_3_ASSET_PIPELINE → STAGE_4_CODE_ITERATION → STAGE_5_COMPLETED`

顶栏 Stepper 按 `currentGame.currentStage` 计算 `completed/active/locked`，已解锁阶段可回溯跳转。

## 对接后端（待办）

真实联调时，替换 `services/mockApi.ts` 与 `hooks/useAgentWebSocket.ts` 为 REST `/api/...` 与 `ws://host/api/ws/{run_id}`；组件与 store 的调用契约保持不变。后端契约见 `backend/api/routes.py`、`backend/orchestrator/machine.py`。
