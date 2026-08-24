<!-- 现有功能介绍 -->

# 头脑风暴->GDD
风险点：Agent 为了把 GDD 写完整，不断向用户提问，最后用户还没看到游戏，已经被需求分析耗尽耐心。

解决方案：
想法
 ↓
快速形成可玩的 V1
 ↓
用户试玩
 ↓
通过实际试玩发现问题
 ↓
V2/V3迭代

版本1是需要把用户想法收缩成一个最小可执行的GDD
迭代就用git tag来驱动

技术：
用户游戏想法
    ↓
AI 头脑风暴
    ↓
识别需要用户确认的问题
    ↓
一次 LLM 生成 Question Plan
    ↓
Temporal Workflow 暂停等待用户
    ↓
前端逐个展示问题
    ↓
用户选择
    ↓
Temporal Signal 接收答案
    ↓
继续下一个问题
    ↓
所有问题完成
    ↓
LLM 汇总需求
    ↓
生成 GDD.md
    ↓
GDD Check
    ↓
Phase 1 完成


持久化状态机流程编排
流程要"暂停等人"、状态必须扛住重启
长耗时外部调用需要超时/重试/取消的精细管理
- spawn claude负责code中最小可执行上下文，是 15–30 分钟级的调用，否则会卡死、堆孤儿进程
生图并行编排 + 限流

# GDD->美术素材
风险点：素材风格不统一，素材数量过多，素材质量不高

解决方案：
| game-art-style | GDD | ART_STYLE.md | 定义统一视觉风格 |
| art-asset-spec | GDD + ART_STYLE | art-assets.md + assets.json | 提取并定义所有美术资产 |
| art-pipeline | assets.json + ART_STYLE | assets/ | Prompt、生图、抠图、处理 |
| art-consistency-check | GDD + ART_STYLE + assets.json + assets | ART_REPORT.md | 完整性和视觉一致性检查 |

发现可优化点：
不是所有美术资产都适合用文生图模型生成。文生图模型适合生成纹理复杂、艺术细节丰富的静态艺术资产；Canvas API 适合处理高频变动、实时计算、矢量几何或程序化控制的动态与交互元素。

# GDD+素材->可玩游戏
风险点：Agent如果一次处理太复杂的问题失败率太高

解决方案：
GDD.md
                   │
                   │
         assets.json + assets/
                   │
                   ▼
        ┌─────────────────────┐
        │ game-architecture   │
        └──────────┬──────────┘
                   │
                   ▼
          GAME_ARCHITECTURE.md
                   │
                   ▼
        ┌─────────────────────┐
        │  game-version-      │
        │      planner        │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │ Version Plan        │
        │                     │
        │ V1.md               │
        │ V2.md               │
        │ V3.md               │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │  game-code-generator│
        └──────────┬──────────┘
                   │
                   ▼
            Superpowers
            Planning
                   │
                   ▼
                  TDD
                   │
                   ▼
              Code Agent
                   │
                   ▼
              Build Game
                   │
                   ▼
             Deploy Vn
                   │
                   ▼
              Playable URL
                   │
                   ▼
             User Playtest
                   │
                   ▼
              Feedback
                   │
                   ▼
          Next Version / Fix


将 GDD 转化为最多 3 个“完整可运行、可试玩、可验证”的游戏版本，并通过用户试玩反馈优化，最终完成 GDD需求。

但是如果想要游戏从串行开发变成并行该怎么办？
加入planner，完整理解游戏拆分出定义公共部分Shared API Contract和可并行Wave，外部串行(依赖)，wave内部并行(Codegen Contracts约束交付)交付给coder spawn完成
┌───────────────────────┐
│   Game Planning       │
│                       │
│ 完整理解游戏          │
│ 拆分版本              │
│ 拆分 Scene/System     │
│ 建立依赖关系          │
└──────────┬────────────┘
           │
           ▼
    Codegen Contracts
           │
     ┌─────┼─────┐
     ▼     ▼     ▼
  Scene   System  UI
 Contract Contract Contract
     │     │     │
     ▼     ▼     ▼
 coder   coder   coder
 spawn   spawn   spawn
     │     │     │
     └─────┼─────┘
           ▼
       Integration

一个wave开发完成后，通过检验再进行下一个wave的开发
Dependency Graph
 ↓
Wave 0
 ↓
tsc
 ↓
Wave 1 parallel
 ↓
tsc
 ↓
Wave 2 parallel
 ↓
tsc
 ↓
Integration
 ↓
Full Test

待优化的点：
引入自动化测试阶段：减少人为测试时间，提高测试覆盖率。不负责判断“游戏好不好玩”，只负责判断“代码是不是健康、游戏能不能正常运行”。

# 用户试玩->优化反馈
用户试玩则负责让游戏变得好玩，和AI交互给出优化反馈。

可添加的点：
用户反馈进入memory记录


# 可视化监测
接入langfuse实现可视化监测
1. 成功率 → Coder Build 成功率
2. 耗时   → Phase / 子阶段耗时
3. Token  → Phase / Skill Token 消耗

skill token检测可方便针对性对skill进行优化
