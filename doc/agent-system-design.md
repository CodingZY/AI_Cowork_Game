# 游戏开发 Agent 系统设计规格书（Agent System Design）

> 利用 `claude_agent_sdk`（接入自部署的 Claude 兼容端点 API key）构造游戏开发 Agent 系统。
>
> 本系统不生成单一游戏，而是**一条可重复运行的游戏开发流水线**：从需求确认到美术资产到可运行 Phaser 游戏，全程人在环（Human-in-the-Loop），支持多游戏。
>
> `doc/game-design-spec.md` 是该系统的一个产物样例（Farmer 游戏设计），不属本规格范围。

---

## 0. 设计总览

### 0.1 两层循环（方案3：混合架构）

- **Orchestrator（后端 Python 状态机）** 拥有阶段、checkpoint、阶段闸。它只认**前端用户对阶段/模块产物的通过/不通过**。
- **阶段内部** 交给对应 agent 的 `query()` 自循环（尤其 Coder 的「写→预览→试玩→反馈→改」），不到阶段闸不烦用户。

**为什么是混合而非单一大循环**：单次 `query()` 跑完整条流水线会让 checkpoint/恢复极难（需持久化 agent 中途推理与会话，SDK 不暴露干净的途中断恢复）。把**阶段边界**交给 Orchestrator（可持久化、可重启续跑），把**阶段内的迭代**交给 agent（有界、可重跑），既得到重启安全的边界，又保留 README 所述开发循环的自主性。

### 0.2 阶段链（状态机）

```
S0 init
 → S1 design   Design Agent（brainstorming 多轮问答 → game-design.md，含游戏名）  闸：用户确认设计
 → S2 art-plan Art Agent（读设计 → 美术素材.md，前端可编辑）                        闸：用户确认素材清单
 → S3 art-gen  Asset Pipeline（自动批量 文生图 + 抠图 → 逐张前端复核）              闸：用户确认素材完成
 → S4 coding   Coder Agent（定数据结构/框架 → 逐模块增量 → 每轮列「可试玩功能清单」+ iframe 预览）  模块闸：通过/改
 → S5 done
```

闸的粒度：
- S1/S2/S3 是**阶段闸**（粗粒度阶段边界，前端用户拍板）。
- S4 是**模块闸**（阶段内更细的同类闸，仍由前端用户拍板），与「阶段间闸由前端用户自己决定」一致。

### 0.3 设计基线（已确认的需求决策）

1. 确认的是 **Agent 系统（meta）** 的需求；Farmer 设计是该系统的一个产物样例。
2. 编排内核：**Python + `claude_agent_sdk`**（`query()` 跑 agent 循环，`HookMatcher` / `PermissionResultAllow` / `PermissionResultDeny` / `ToolPermissionContext` 做拦截与审批），指向自部署的 Claude 兼容端点。
3. 三角色（Design / Art / Coder）+ Asset Pipeline 映射为「不同 system prompt + 工具集 + 权限配置」的独立 `query()` 运行，靠磁盘文件交接。
4. HITL：**要持久化层 + checkpoint**，进程重启能续跑。
5. 阶段闸：**前端展示产物 → 通过进下一步 / 不通过改到通过**；高危动作（付费 API、写源码）另走细粒度 SDK permission 沙箱。
6. 前端：完整 SPA（React 18 + Vite + TypeScript），后端 FastAPI。
7. 外部 API：凭证放后台 `.env`；**不限流**；用户确认 `美术素材.md` 后自动批量生成 + 抠图，再逐张前端复核。
8. Coder 试玩：**iframe 内嵌**预览运行中的 Phaser 游戏 + **可试玩功能清单**面板。
9. 持久化：**MySQL**。
10. 多游戏：产物落 `Games/<game-name>/`，游戏名在 S1 设计阶段定。

---

## 1. Agent 角色与权限

每个角色 = 一次 `query()`，带独立 system prompt + 工具集 + **权限配置**（`PermissionResultAllow/Deny` + `HookMatcher`）。

| 角色 | 工具 | 写权限作用域 |
|---|---|---|
| **Design Agent**（编码 obra/superpowers 的 brainstorming 方法论） | `read_file`、`write_file(game-design.md)`、`ask_user` | 仅 `Games/<name>/docs/game-design.md` |
| **Art Agent** | `read_file`、`write_file(美术素材.md)` | 仅 `Games/<name>/docs/美术素材.md` |
| **Asset Pipeline** | `generate_image(wan2.7)`、`style_transfer`、`cutout(腾讯)`、`save_png` | 仅 `Games/<name>/assets/` |
| **Coder Agent** | `read_file`、`write_file(src/**)`、`run_dev_server`、`list_playable` | 仅 `Games/<name>/src/` |

### 1.1 两层审批分清

- **人审（前端闸）**：阶段产物 + 模块试玩。**阻塞 Orchestrator 推进**。用户在前端对产物点「通过 / 不通过 + 反馈」。
- **机审（SDK permission，非弹窗）**：仅做**沙箱**——按上表限定每个 agent 能写哪个目录、能调哪些工具，越界即 `Deny`。不是逐调用找人点确认。

`HookMatcher` 用于：工具调用前后打日志 / 推前端进度流（让用户看见 agent 在干什么），以及写源码前的安全校验。

### 1.2 Design Agent 的 brainstorming 方法论

Design Agent 的 system prompt 即编码 obra/superpowers 的 brainstorming 方法论：

- 一次只问一个问题（多选优先）。
- 在提具体设计前，提出 2-3 个方案及权衡与推荐。
- 分节呈现设计，每节后求确认。
- 通过后写出 spec（即 `game-design.md`）。
- 游戏名在 S1 阶段确定，写入 `game-design.md` 标题；Orchestrator 据此建 `Games/<game-name>/` 目录（`<game-name>` 为游戏名的目录安全 slug：小写、空格转连字符、剔除非法字符）。

它是「确认需求」环节本身被 agent 化的镜像——把人脑做需求确认的过程，变成 agent 跑出 `game-design.md`。

### 1.3 Asset Pipeline（自动批量）

用户在前端确认 `美术素材.md` 后，Pipeline 即按清单**自动批量**「文生图 + 抠图」，不逐张审批、不限流。生成完成后每张图在前端卡片展示，提供操作：【直接保存】/【抠图并保存】/【修改 Prompt 重试】；另支持风格转绘面板（上传风格参考图 + 结构参考图）。

---

## 2. 持久化与 checkpoint

### 2.1 真相源分层

- **Orchestrator 状态** → **MySQL**（阶段、子状态、待审批闸、最近产物指针、用量记账等）。
- **阶段产物** → **文件系统**（`Games/<name>/docs/*.md`、`assets/`、`src/`）。文件即天然 checkpoint 产物。

### 2.2 不持久化 agent 中途推理

agent 在阶段内是无界的但**可重跑**——重启时按 Orchestrator 状态 + 最近产物重入当前阶段。拒绝/崩溃 = 带反馈或带上一版产物重调 `query()`。这是采用方案3（混合）而非单一长循环的核心原因。

### 2.3 待审批队列落 MySQL

进程重启后，前端重连 WebSocket 即可看到「卡在哪个闸、等什么」，并继续审批。

### 2.4 状态可重建

MySQL 损坏可由文件产物 + 日志重建阶段进度（以产物存在性反推阶段）。

---

## 3. 前端（完整 SPA 结构）

**React 18 + Vite + TypeScript**，左侧阶段进度条，右侧按阶段切换工作台：

- **S1 / S2 工作台**：Markdown 编辑器（可编辑 `game-design.md` / `美术素材.md`）+ Design Agent 问答面板（`ask_user` 问题在此答）。
- **S3 工作台**：素材看板，每张图卡片 = 缩略图 + 操作【直接保存】/【抠图并保存】/【修改 Prompt 重试】+ 风格转绘面板（上传风格参考图 + 结构参考图）。
- **S4 工作台**：**iframe 内嵌预览**运行中的 Phaser 游戏 + **「可试玩功能清单」面板**（Coder 每轮列出已实现玩法点）+ 反馈输入框 + 模块列表（通过 / 改）。
- **全局**：agent 实时进度流面板（WebSocket 推送的工具调用 / 思考日志）。

### 3.1 协议

- **REST**：取状态 / 文档 / 资产、提交编辑、闸通过 / 不通过 + 反馈。
- **WebSocket**：进度流、问答、生成进度、预览就绪。
- **iframe**：src 指向后端托管的当前游戏 dev_server（Phaser 静态预览）。

---

## 4. 技术栈与目录结构

### 4.1 技术栈

- **后端**：Python 3.11 · FastAPI · uvicorn · `claude_agent_sdk` · httpx（阿里百炼 / 腾讯云）· Pillow · MySQL（SQLAlchemy + aiomysql）· python-dotenv。
- **前端**：React 18 · Vite · TypeScript · WebSocket。
- **游戏**：Phaser.js（由生成的 `src/index.html` 加载，后端 StaticFiles 托管当前游戏的 `src/`）。

### 4.2 目录结构

```
AI_Cowork_Game/
├── README.md
├── game-design-spec.md     # 参考交付物样例（Farmer 游戏设计：阶段1 交付格式参考 / 测试夹具）
├── doc/                     # 设计文档（agent-system-design.md）
├── backend/
│   ├── orchestrator/        # 状态机 + checkpoint（状态落 MySQL）
│   ├── agents/              # 四角色：system prompt + 工具 + 权限
│   ├── pipeline/            # 图像生成 / 抠图
│   ├── api/                 # FastAPI REST + WS
│   ├── persistence/         # MySQL
│   └── .env                 # 阿里 / 腾讯 / 自部署端点 key
├── frontend/                # React SPA
└── Games/                   # 多游戏，每个一个目录（按游戏名命名）
    └── <game-name>/
        ├── docs/
        │   ├── game-design.md       # 阶段1产出
        │   └── 美术素材.md           # 阶段2产出
        ├── assets/
        │   ├── raw/                 # 阶段3产出：API 生成的原图
        │   └── processed/          # 阶段4产出：AI 抠图后的透明 PNG 资产
        ├── src/                     # 阶段5产出：游戏源码
        │   ├── index.html
        │   ├── js/
        │   │   ├── main.js
        │   │   ├── player.js        # 增量模块代码
        │   │   └── map.js
        │   └── assets_map.js        # 资产映射配置表
        └── dev_server.py            # 该游戏的本地预览服务（iframe 指向它）
```

> 顶层不再有 `assets/`、`src/`（已删，避免与 `Games/` 冗余）；所有游戏产物均在 `Games/<game-name>/` 下。

---

## 5. 错误处理与测试

### 5.1 错误处理

- **外部 API 失败**（wan2.7 / 抠图）：退避重试 → 仍败则前端图卡报错 → 用户可【重试】。
- **agent `query()` 异常**：Orchestrator 捕获、记日志、前端提示，允许从最近产物重跑当前阶段。
- **写越界**：SDK permission `Deny`，记日志，agent 收到拒绝后调整重试。

### 5.2 测试

- **Orchestrator 状态机**：状态转移 + 闸逻辑单测。
- **agent runner**：mock SDK，测工具接线 + 权限作用域（越界被 Deny）。
- **Asset Pipeline**：mock HTTP，测 生成 → 抠图 → 存盘 + 重试 + 风格转绘。
- **前端组件**：工作台切换、问答、素材看板、可试玩清单。
- **Coder dev loop**：fixture 项目，测 写代码 → 托管 → 预览 URL → 列可试玩清单。

---

## 6. 范围与子项目拆分

本 spec 覆盖**整体架构与模块边界**。落地建议拆为以下子项目，各自再走 spec → plan → 实现循环：

1. **Orchestrator + persistence**：状态机、checkpoint、MySQL schema、闸协议。
2. **agent runner 骨架**：`claude_agent_sdk` 接线、四角色 system prompt + 工具 + 权限沙箱、HookMatcher 进度流。
3. **Asset Pipeline**：阿里 wan2.7、腾讯抠图、风格转绘、批量编排、退避重试。
4. **前端 SPA**：四阶段工作台、Markdown 编辑、问答面板、素材看板、可试玩清单、WS 进度流。
5. **Coder dev loop**：dev_server 托管、iframe 预览、可试玩清单输出、模块闸。

各子项目的实施计划由后续 `writing-plans` 环节分别产出。
