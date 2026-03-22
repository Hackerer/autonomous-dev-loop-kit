# Autonomous Dev Loop Kit PRD

Version: 1.0
Date: 2026-03-22

## 1. 背景

`autonomous-dev-loop-kit` 的目标不是把一套脚本复制进目标项目，也不是把目标项目改造成“带 kit 的仓库”。它的本质是一个位于 **Claude Code / Codex 与目标项目之间的中间控制层**，用于提升 AI CLI 在真实项目中的自动化迭代能力、可审计性、可验证性和发布稳定性。

没有这个 Kit，Claude Code / Codex 依然可以改代码，但自动化程度低、过程不一致、状态容易散落、发布行为不稳定。

有了这个 Kit，Claude Code / Codex 仍然只是执行器，但它们的行动会被统一的协议、状态、日志、报告、验证和发布门禁约束，从而形成可重复、可恢复、可审计的自动化开发闭环。

## 2. 目标

### 2.1 总目标

构建一个 **workspace-local** 的自治开发控制平面：

- Kit 自己保存所有控制状态、知识、日志、报告、发布产物和项目级索引
- 目标项目仓库只承载业务代码变更和 Git 提交
- Claude Code / Codex 通过 Kit 运行协议执行目标项目，而不是把 Kit 逻辑安装进目标项目
- 默认不侵入目标项目目录
- 默认不要求目标项目理解 Kit 的内部结构

### 2.2 设计目标

- 保持所有现有功能，不减少能力
- 将所有项目相关知识和过程数据统一收敛到 Kit 工作区
- 按项目建立独立目录，避免不同目标项目的数据混杂
- 支持外部目标仓库执行
- 保留 legacy copy-assets 作为迁移兼容路径，但不作为默认路径
- 保持 Claude Code 和 Codex 两边的 skill 入口一致
- 保持 skill 入口薄、引用分层清晰、复杂逻辑外置

## 3. 问题定义

当前需要解决的问题有四类：

1. **侵入性**
- 旧实现会把 Kit 脚本、状态或辅助文件写入目标项目
- 这会污染对方仓库，也会让目标项目承担不属于它的控制逻辑

2. **状态分散**
- 项目相关数据散落在多个位置，会导致：
  - 无法统一查看历史
  - 无法稳定恢复上下文
  - 不同项目的数据互相覆盖或混淆

3. **执行对象不清晰**
- 需要明确：
  - 哪部分是 Kit 自己的控制面
  - 哪部分是目标项目
  - 哪部分是 Claude Code / Codex 的行为约束

4. **自动化层次不足**
- 需要把“AI 会改代码”升级成“AI 按协议迭代、验证、记录、发布”
- 同时不能让自动化流程吞掉目标项目本身的简洁性

## 4. 关键原则

### 4.1 中间层原则

Kit 是中间层，不是目标项目的一部分。

- Kit 负责协议、记忆、门禁、日志、报告、发布编排
- Claude Code / Codex 负责实际执行
- 目标项目只负责承载代码变更和 Git 历史

### 4.2 零侵入默认原则

默认情况下：

- 不复制 Kit 资产到目标项目
- 不要求目标项目存在 Kit 脚本
- 不要求目标项目保存 Kit 状态
- 不要求目标项目理解 Kit 的目录结构

### 4.3 项目级隔离原则

每个目标项目必须有自己的 Kit 工作区目录，所有项目级资料都写入该目录。

### 4.4 单一 skill 原则

Claude 侧和 Codex 侧都应该保持一个 skill 入口，不拆分为多个模式或多个 skill。

### 4.5 保持能力原则

架构重构只能改变归属和组织方式，不能削弱现有能力。

## 5. 用户与场景

### 5.1 主要用户

1. **开发者**
- 通过 Claude Code / Codex 让 Kit 驱动目标项目迭代
- 希望低摩擦地连续做多个版本

2. **维护者**
- 需要回看每个项目的历史决策、报告、验证和发布记录

3. **评审者**
- 需要检查某次迭代为什么通过、为什么被阻断、为什么晋级

### 5.2 典型场景

1. 用户在另一个文件夹里 coding，希望通过 Codex 调用 Kit 迭代目标仓库
2. 用户只说“循环 5 次”，希望 Kit 自动持久化 session 并推进多个版本
3. 用户不希望目标仓库里出现 Kit 文件
4. 用户希望所有项目相关知识、状态、日志、报告都能在 Kit 仓库内追踪
5. 用户希望 Claude Code 与 Codex 共享同一套协议和状态约束

## 6. 范围

### 6.1 In Scope

- 对外部目标仓库进行自动化迭代
- 通过环境变量或显式参数指定目标仓库
- 将项目级状态、日志、报告、release 记录、项目数据保存到 Kit 工作区
- 按项目建立独立目录
- 保留委员会、研究、验证、发布、实验层等现有功能
- 支持 no-copy 默认安装和 legacy copy-assets 兼容路径
- 支持 Claude Code 和 Codex 两边的一致入口

### 6.2 Out of Scope

- 将目标项目改造成 Kit 仓库
- 要求目标项目内长期保存 Kit 的脚本和模板
- 把 Kit 变成通用任务代理
- 把多个模式暴露给用户选择
- 去掉验证门禁或发布门禁

## 7. 信息架构

### 7.1 Kit 工作区

Kit 仓库是控制面本体，负责保存：

- skill 入口
- references
- scripts
- 配置
- 通用模板
- 项目级工作区索引

### 7.2 项目级工作区

每个目标项目在 Kit 文档目录下创建一个独立目录：

```text
docs/projects/<project-id>/
```

其中 `<project-id>` 应该由目标项目路径派生，具备：

- 人类可读的 slug
- 稳定的短哈希
- 同名项目路径下的唯一性

### 7.3 建议目录结构

每个项目目录建议包含：

```text
docs/projects/<project-id>/
  .agent-loop/
    config.json
    state.json
    backlog.json
    data/
      usage-log.jsonl
      project-data.json
      data-quality.json
      last-validation.json
  docs/
    reports/
    releases/
    reviews/
  snapshots/
  artifacts/
  notes/
```

说明：

- 目录可以先逐步落地，不要求一次性全部启用
- 但最终所有项目相关知识和过程记录都应能归档到该空间

## 8. 数据归属规则

### 8.1 必须写入 Kit 工作区的内容

- session 状态
- release 状态
- backlog
- review state
- committee 输出
- evaluator brief
- validation 结果
- task report
- release report
- usage log
- project data snapshot
- data-quality 输出
- escalation 结果
- publish 事件

### 8.2 只属于目标项目的内容

- 源码修改
- Git commit
- Git push
- 目标项目自己的业务配置
- 目标项目需要长期保留的业务文档

### 8.3 禁止默认写入目标项目的内容

- Kit 脚本
- Kit skill 文件
- Kit references
- Kit templates
- Kit 状态文件
- Kit 日志文件
- Kit 报告控制文件

## 9. 运行模型

### 9.1 控制流

```text
User
  -> Claude Code / Codex
  -> Autonomous Dev Loop Kit
  -> Target project repo
```

### 9.2 执行方式

Kit 本身不直接“替代” Claude Code / Codex，而是：

- 提供 skill 与协议
- 提供脚本与状态机
- 提供中间层存储与审计
- 提供发布门禁

Claude Code / Codex 负责：

- 打开目标项目目录
- 修改目标项目文件
- 执行验证
- 执行 Git 提交/发布

### 9.3 目标指定方式

支持以下方式指定目标项目：

- 显式参数
- 环境变量 `AUTONOMOUS_DEV_LOOP_TARGET`
- 当前执行目录

当目标项目不在 Kit 仓库内时，必须明确指定目标。

## 10. 功能需求

### 10.1 安装与注册

**FR-1**
- 默认安装不得把 Kit 文件复制到目标项目

**FR-2**
- 安装动作必须在 Kit 工作区里写入该项目的记录

**FR-3**
- 兼容路径可以通过显式开关启用 legacy copy-assets

**FR-4**
- 安装后，目标项目不应自动多出 Kit 的脚本目录或状态目录

### 10.2 项目识别

**FR-5**
- 系统必须能根据目标项目路径生成稳定的 project-id

**FR-6**
- 同一个目标路径应始终映射到同一个 project-id

**FR-7**
- 不同目标路径即使同名，也必须通过哈希区分

### 10.3 状态持久化

**FR-8**
- session、release、review、validation、progress 状态必须保存到项目级工作区

**FR-9**
- 状态读取必须优先读取对应项目的工作区，而不是目标仓库根目录

**FR-10**
- 状态变更必须支持恢复、继续、回退、重跑

### 10.4 日志

**FR-11**
- 所有 usage log 必须写到项目级工作区

**FR-12**
- 每条日志必须记录：
  - workspace root
  - target repo root
  - event type
  - session context
  - release context
  - goal context
  - current iteration

**FR-13**
- 日志分析工具必须支持按项目分析，也必须支持聚合多个项目

### 10.5 报告

**FR-14**
- 每次迭代必须生成 task report

**FR-15**
- 每个 bundled release 完成后必须生成 release report

**FR-16**
- 报告必须保存在项目级工作区内

**FR-17**
- 报告不得依赖目标仓库里的 Kit 文件存在

### 10.6 验证与门禁

**FR-18**
- 必须保留完整验证门禁

**FR-19**
- 必须保留 committee review gate

**FR-20**
- 必须保留 evaluator / readiness gate

**FR-21**
- 发布前必须通过真实 validation

**FR-22**
- 发布前必须有可追踪的 review state 和 evaluator 状态

### 10.7 发布

**FR-23**
- 发布行为必须作用于目标项目自己的 Git 仓库

**FR-24**
- publish 不能把变更提交到其他项目的 remote

**FR-25**
- 完成 task 迭代和 bundled release 时，必须记录到项目级工作区

### 10.8 实验层

**FR-26**
- 保留 `base / candidate / promote` 逻辑

**FR-27**
- 默认 baseline 使用已晋级版本

**FR-28**
- candidate 只有在优于 base 时才 promote

**FR-29**
- 实验层是 Kit 内部能力，不应侵入目标项目

### 10.9 skill 入口

**FR-30**
- Claude Code 和 Codex 仅使用一个 skill 入口

**FR-31**
- skill 必须是薄入口

**FR-32**
- skill 正文只保留触发、最短路径、硬门禁和引用入口

**FR-33**
- 复杂协议必须下沉到 references 和 scripts

## 11. 非功能需求

### 11.1 可审计性

- 所有关键行为都必须可以通过状态文件、日志和报告追踪

### 11.2 可恢复性

- session 中断后应能继续
- 发布失败后不应污染已完成的状态

### 11.3 可扩展性

- 新项目不应要求修改 Kit 主流程
- 项目级工作区结构应允许按项目增加补充文件

### 11.4 兼容性

- legacy copy-assets 可以保留
- 但默认路径必须保持零侵入

### 11.5 一致性

- Claude Code 和 Codex 的协议必须保持一致
- Kit 文档、skill、脚本、验证器的语义必须一致

## 12. 工作流要求

### 12.1 标准循环

1. 确定目标项目
2. 读取项目级工作区状态
3. 收集项目数据
4. 评分数据质量
5. 渲染委员会上下文
6. 进行 research 和 scope review
7. 记录 review state
8. 生成 evaluator brief
9. 判定 readiness
10. 实施改动
11. 运行验证
12. 写 report
13. 发布 iteration
14. 进入下一轮或结束 release

### 12.2 bundled release 循环

1. 确认 release 主题
2. 选择多个 goal
3. 在 release 内逐个执行 task iteration
4. 每个 iteration 都验证和记录
5. release 完成后生成 release report
6. 发布 release closeout

### 12.3 外部目标模式

当工作目录不是目标项目本身时：

- 目标必须显式指定
- 所有控制信息仍然在 Kit 工作区
- 目标项目只接收实际代码变更和 Git 提交

## 13. 验收标准

### 13.1 行为验收

- 默认安装不会把 Kit 文件复制进目标项目
- 项目级状态和日志都存到 `docs/projects/<project-id>/`
- 外部目标可以通过环境变量或显式参数驱动
- Claude Code 和 Codex 使用同一套协议
- 保留所有现有功能
- 验证仍然通过

### 13.2 结构验收

- Kit 仓库是控制面
- 每个项目在 `docs/projects/<project-id>/` 下有自己的记录空间
- 不同项目的数据不会混在一起
- 目标项目目录本身不需要长期保存 Kit 资产

### 13.3 质量验收

- `validate-kit.py` 必须通过
- 技能入口必须保持薄
- 报告与状态路径必须一致
- 日志分析必须能按项目归档

## 14. 迁移要求

### 14.1 从旧 repo-local 模型迁移

旧模型的特点：

- 状态写在目标项目里
- 日志写在目标项目里
- 运行时默认依赖目标目录中的 `.agent-loop`

新模型要求：

- 状态和日志写回 Kit 工作区
- 目标项目只保留代码与 Git
- 通过环境变量或显式参数将目标项目接入 Kit

### 14.2 兼容迁移

为了不破坏已有安装，可以保留：

- `--copy-assets`
- legacy 目标内 `.agent-loop` 运行方式

但这些必须是显式兼容路径，不能成为默认行为。

## 15. 风险与约束

### 15.1 风险

- 工作区路径迁移后，旧脚本可能仍然依赖目标仓库内的状态路径
- 日志分析若不区分 workspace / repo，容易误读数据归属
- 目标路径与 workspace 路径的边界如果不统一，容易导致状态分裂

### 15.2 约束

- 不允许引入第二套 skill 模式
- 不允许默认侵入目标仓库
- 不允许减少现有功能
- 不允许放弃验证门禁

## 16. 未决问题

1. `docs/projects/<project-id>/` 下是否需要进一步标准化子目录命名
2. 旧的 repo-local 历史数据是否需要自动迁移到新 workspace 结构
3. 是否需要为每个项目维护独立的索引文件，便于跨项目检索
4. `AUTONOMOUS_DEV_LOOP_TARGET` 和 `AUTONOMOUS_DEV_LOOP_WORKSPACE` 是否需要成为正式对外文档的一部分
5. 是否需要为项目级目录提供清理与归档策略

## 17. 结论

这个 Kit 的产品定位应当是：

- 一个面向 Claude Code / Codex 的自治开发控制平面
- 一个默认零侵入的中间层
- 一个以项目为单位隔离状态和知识的工作区系统
- 一个保留完整验证、报告、发布、实验晋级能力的自动化开发框架

它的核心不是“安装到项目里”，而是“在 Kit 仓库里管理项目”。

## 18. 执行过程

这一部分描述一次真实运行从触发到发布的完整执行链路。目标是让实现者、维护者和评审者都能清楚知道：

- 谁在做事
- 事先读什么
- 中间写到哪里
- 失败时停在哪一步
- 哪些内容属于 kit workspace
- 哪些内容真正作用到目标仓库

### 18.1 执行角色

| 角色 | 职责 |
| --- | --- |
| User | 发出“开始循环”“循环 N 次”“继续下一版”等请求 |
| Claude Code / Codex | 读取 skill，调用脚本，编辑目标仓库，执行验证和 Git 操作 |
| Kit | 提供协议、状态机、日志、报告、发布门禁和项目级工作区 |
| Target Repo | 仅承载真实代码修改和 Git 历史 |

### 18.2 触发入口

当用户输入下面任一类请求时，必须触发该 Kit：

- 自主循环开发
- 自动迭代开发
- 继续下一版
- 循环 3 次、做 5 轮、run 3 iterations、ship 2 versions 这类 loop-count 请求

触发后，Claude Code / Codex 先加载 skill，然后再决定执行对象。

### 18.3 目标解析

执行前必须明确目标仓库：

1. 如果当前工作目录本身就是目标项目，则直接使用当前目录
2. 如果目标项目在外部目录，则必须显式设置 `AUTONOMOUS_DEV_LOOP_TARGET=/path/to/project`
3. 如果还需要将控制状态从目标仓库完全外置，则可以额外设置 `AUTONOMOUS_DEV_LOOP_WORKSPACE=/path/to/kit/project-folder`

解析结果分成三部分：

- `kit root`：Kit 仓库本身
- `target root`：真正被修改的目标仓库
- `workspace root`：该项目在 Kit 里的控制面目录，默认是 `docs/projects/<project-id>/`

### 18.4 初始化阶段

启动时必须先完成初始化，再进入任何实际改动：

1. 读取 `PLANS.md`
2. 读取 `config.json`
3. 读取或初始化项目级 `state.json`
4. 读取或初始化项目级 `backlog.json`
5. 确认目标仓库和 workspace root 映射关系正确
6. 如果是用户显式要求的 loop count，先持久化 session 目标

这一阶段的输出应写入项目级工作区，而不是目标仓库根目录。

### 18.5 数据采集阶段

如果项目数据缺失或过期，先做数据采集：

1. 扫描目标仓库源码和工具信号
2. 读取目标仓库的 `PLANS.md`
3. 读取 Git 分支和 remote 信息
4. 生成 project data snapshot
5. 评分 data quality
6. 将结果写入项目级工作区

这里的关键点是：

- 数据来源是目标仓库
- 数据归档位置是 Kit 的项目级工作区

### 18.6 委员会与研究阶段

在选择目标 goal 之前，必须先完成委员会与研究链路：

1. 渲染委员会上下文
2. 进行 research
3. 判断 research 是否足够
4. 记录 committee feedback
5. 记录 scope decision
6. 如有需要，记录 evaluator brief 前置上下文

如果 research 明确要求 `need_more_context`，必须停住，不允许直接跳到实施。

### 18.7 目标选择阶段

在研究与门禁通过后：

1. 从 backlog 中选择下一条 goal
2. 将 goal 写入项目级工作区 `state.json`
3. 如果当前有 bundled release，goal 必须属于该 release 的范围内
4. 如果 release 已经完成，必须先 closeout 再进入下一 release

### 18.8 评审与准备阶段

在实施前，必须形成完整的预实施材料：

1. capture-review
2. render-evaluator-brief
3. score-evaluator-readiness
4. assert-implementation-readiness

这一阶段决定能不能进入实施。

如果 evaluator 结果或 review state 不符合门禁，必须停在这里，不得写代码。

### 18.9 实施阶段

通过准备门禁后，Claude Code / Codex 才能修改目标仓库：

1. 打开目标仓库
2. 修改最小的 coherent change set
3. 必要时补充测试
4. 保持变更与当前 goal 一致

这里是唯一一个应当直接作用于目标项目业务文件的阶段。

### 18.10 验证阶段

改完后，必须运行真实验证：

1. 读取项目级 workspace 中的 validation 配置
2. 执行 lint / test / build / e2e 等配置命令
3. 写入 validation 结果
4. 若失败，记录失败原因并停住

验证失败时，不能直接发布，也不能把失败当作已完成。

### 18.11 报告阶段

验证成功后：

1. 生成 task report
2. 将 report 路径写入项目级 workspace state
3. 报告中必须包含：
   - 本轮 goal
   - 实际修改
   - 验证结果
   - review / evaluator 结论
   - 失败与阻断原因
   - 对下轮的建议

### 18.12 发布阶段

通过验证并写完报告后：

1. 在目标仓库执行 Git add / commit / push
2. 将 publish 事件写入项目级工作区 usage log
3. 更新项目级 state、backlog 和 release history
4. 如果当前 iteration 属于 bundled release，则更新 release progress

发布必须作用于目标仓库自己的 Git remote，不得推送到其他项目。

### 18.13 Release Closeout

当一个 bundled release 的所有 goal 都完成：

1. 写 bundled release report
2. 验证 release 层总结
3. 发布 release closeout
4. 将 release 记入 history
5. 进入下一个 release 或结束 session

### 18.14 失败与恢复

如果任何阶段失败：

- 数据不足则回到数据采集阶段
- research 不足则停在委员会阶段
- readiness 不足则停在评审阶段
- validation 失败则停在实施后、发布前
- Git target 不清晰则停在发布前

系统必须允许从项目级 workspace 恢复，而不是依赖对话记忆。

### 18.15 一次运行的实际顺序

下面是一个最典型的实际顺序：

1. 用户触发 skill
2. 解析目标仓库
3. 解析项目级 workspace
4. 记录或继续 session
5. 采集项目数据
6. 评分数据质量
7. 渲染委员会
8. 进行 research
9. 记录 scope decision
10. 生成 evaluator brief
11. 评估 readiness
12. 选择 goal
13. 修改目标仓库
14. 运行验证
15. 写 task report
16. publish iteration
17. 如果 release 完成，写 release report 并 closeout
18. 进入下一轮或结束

### 18.16 最重要的执行边界

整个过程中必须始终保持以下边界：

- Kit 保存知识、状态、日志、报告
- Target Repo 保存代码变更和 Git 历史
- Claude Code / Codex 执行步骤，不定义规则

如果这三者边界被混淆，就意味着实现不符合本 PRD。
