# 目标
利用claude_agent_sdk（接入自部署的API key）构造游戏开发Agent
1.superpower结合用户给的游戏思路进行需求确认，落地为game-design.md
2.game-design.md分析游戏需要的美术资产（游戏开场、角色、NPC、地图、物品等等），落地为美术素材.md，并在前端展示，可供用户修改编辑
3.用户确认后，调用第三方API进行素材生成，前端展示，用户可以选择保留或调整，保留则下载到本地，调整则让用户输入调整的prompt然后调用API重新生成，可以支持风格转绘（选择风格图片和待转绘图片）调用API进行生成，保存为png
4.素材生成后调用AI抠图API保存为png
5.代码生成：确认数据结构、代码框架、增量开发模块，每一模块开发完成，启动网页让开发者试完，并给出回馈。如果正确进行下一模块开发，如果则根据提示进行修改知道用户确认正确。

# 系统架构图
前端 GUI 界面：Markdown编辑器 / 素材看板 / Web游戏预览 (WebSocket / REST API)
Agent Orchestrator (主控引擎)  
│  - 状态管理 (State Machine)
│  - 人工干预中断/恢复 (Human-in-the-Loop Interruption) 

Design Agent：需求确认
作用:采用多轮问答（游戏类型、核心玩法、美术风格、胜利条件等），主动引导用户补全要素。当需求完整后，自动生成并保存 game-design.md，交由前端渲染呈现。
skill:superpower

Art Agent：资产规划
读取 game-design.md，拆解出明确的美术清单，输出 美术素材.md。每个资产包含：[ID]、[类别]、[描述]、[推荐生成Prompt：包括但不限于绘画风格、背景要求：纯白色背景，无场景，无地面，无阴影背景，无边框，无UI，仅保留角色本体。]、[尺寸/透明度要求]。
• 开场/背景（如 title_screen.png, level1_bg.png）
• 角色与 NPC（如 hero_idle.png, npc_merchant.png）
• 地图与建筑物（如 wall_tile.png, floor_tile.png）
• 物品与 UI（如 coin.png, hp_bar.png）

Asset Pipeline：生成与抠图
根据资产清单，调用图像生成 API，支持风格转绘与自动抠图。
[素材 Prompt] ──► [文生图 API (Flux / SD)] ┐
                                                     ├─► [生成图预览] ──► [AI 抠图 API (RMBG)] ──► [导出透明 PNG]
[待转绘图 + 风格图] ──► [图生图/风格转绘 API]   ┘
调用[大模型服务平台百炼控制台](https://bailian.console.aliyun.com/cn-beijing/?tab=api&utm_content=se_1023032762#/api/?type=model&url=3026980)的wan2.7-image进行图片生成
调用[数据万象 智能抠图_腾讯云](https://cloud.tencent.com/document/product/460/80907?from=console_top_search)进行智能抠图
前端交互：
• 提供“风格转绘”面板：支持上传“风格参考图”和“结构参考图”。
• 每一张生成的图片展示在前端卡片中，提供操作按键：【直接保存】/【抠图并保存】/【修改 Prompt 重试】。
Coder Agent
技术栈固定为 HTML + JavaScript + Phaser.js，最终产物可直接在浏览器运行
项目定位为中大型游戏，架构设计必须满足三大核心要求：运行高性能、功能高扩展性、代码高可维护性
所有代码必须附带中文注释，每阶段输出都要有通俗易懂的功能说明
模块化组件设计（玩家、NPC、UI、数值系统等独立模块） 
资源分类管理（图片、音频等）
定义游戏数据结构、代码框架，进行功能增量开发开发与运行验证。将读取 game-design.md将游戏拆分成几大功能模块，如之后在种植、喂养、NPC。
┌─────────────────────────────────────────────────────────┐
│                   模块开发循环 (Dev Loop)                │
│                                                         │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────┐ │
│  │ 编写/更新代码 ├────► 启动预览服务器 ├────► 用户试玩   │ │
│  └──────────────┘     └──────────────┘     └────┬─────┘ │
│         ▲                                       │       │
│         │              根据反馈修改              │       │
│         └───────────────────────────────────────┴───────┤
│                                                (通过)   │
│                                                   ▼     │
│                                            进入下一模块  │
└─────────────────────────────────────────────────────────┘
Agent 运行过程中产生的中间产物
game-project-root/
├── docs/
│   ├── game-design.md       # 阶段1产出：游戏设计文档
│   └── 美术素材.md           # 阶段2产出：美术资产需求清单
├── assets/
│   ├── raw/                 # 阶段3产出：API 生成的原图
│   └── processed/           # 阶段4产出：AI 抠图后的透明 PNG 资产
├── src/                     # 阶段5产出：游戏源码
│   ├── index.html           # 网页入口
│   ├── js/
│   │   ├── main.js          # 核心流程
│   │   ├── player.js        # 增量模块代码
│   │   └── map.js
│   └── assets_map.js        # 资产映射配置表
└── dev_server.py            # Agent 调用的本地测试 Web Server
