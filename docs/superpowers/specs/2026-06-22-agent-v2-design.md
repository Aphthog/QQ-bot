# Agent V2 设计规格

## 1. 概述

将 qq-bot 从"手写 tool dict 的硬编码 ReAct 循环"重写为一个 **通用能力驱动的自主 agent**。

核心变化：

- 工具从 8 个专用 → **3 个通用核心工具**。LLM 自主决定如何组合完成任意任务，不再穷举 if-else。
- 一个多模态 LLM（GLM-4.6V，可替换）覆盖文本对话、图片理解、工具调用。
- 结构化三层记忆（短期对话 + 长期语义记忆 + 用户画像）。
- 可扩展的 AgentLoop 设计——单体够用，预留 MessageBus 接口将来无缝升级到 sub-agent / 多 agent。
- Web 管理面板 + 权限控制 + 定时任务。

---

## 2. 技术栈

| 层级 | 选型 | 说明 |
|------|------|------|
| 消息协议 | QQ → NapCat/LLOneBot → OneBot V11 | 不变 |
| 核心框架 | NoneBot2（纯适配层） | 不变 |
| LLM | **GLM-4.6V**（默认） / Qwen2.5-VL（备选） | 可插拔，改配置即可切换 |
| 搜索 | **SearXNG**（默认） / Tavily（备选） | 可插拔，改配置即可切换 |
| 生图 | 外部 API | LLM 自主决定调用 `generate_image` 工具 |
| 存储（结构化） | SQLite | 嵌入式，零运维 |
| 存储（向量） | ChromaDB | 嵌入式，零运维 |
| 管理后台 | FastAPI | 复用 NoneBot2 内置 driver |
| 定时任务 | nonebot-plugin-apscheduler | 不变 |

### 2.1 为什么选 GLM-4.6V

| 维度 | GLM-4.6V | Qwen2.5-VL | 说明 |
|------|------|------|------|
| 文本对话 | ✅ | ✅ | 两者都够用 |
| 图片理解 | ✅ | ✅ | 两者都原生多模态 |
| Tool Calling | ✅ **原生视觉 tool call** | ⚠️ 文档较少 | GLM-4.6V 独有：看图直接调工具 |
| Agent 基准 | **WebVoyager 81%** | ~48% | 多步任务执行显著领先 |
| 中文 | ✅ 国产，中文天然友好 | ✅ | 两者都是中文优先 |
| 价格 | ¥1/M 入 ¥3/M 出 | ¥1.15/M 入 ¥4.6/M 出 | GLM 略便宜 |
| 免费版 | **Flash 版完全免费** | 无 | 开发阶段零成本 |
| 上下文 | 128K | 131K | 两者都够用 |

GLM-4.6V 被形容为"偏科生"——结构化任务（OCR、前端复刻、商品比价）很强，原生视觉 tool calling 是其独有优势。短板：模糊指令理解偶有偏差、梗图文化理解偏浅。对 QQ 群 bot 场景，这些短板不致命。

### 2.2 为什么选 SearXNG

| 维度 | SearXNG | Tavily | DuckDuckGo (V1) |
|------|------|------|------|
| 中文搜索 | ✅ 聚合 Google+Bing+百度 | ⚠️ 英文产品，中文未验证 | ❌ 中文弱 |
| AI 优化 | 需自处理（searxng-cli） | ✅ 专为 LLM 设计 | ❌ |
| 成本 | **免费无限** | 1000 次/月免费 | 免费但质量差 |
| 部署 | Docker 自部署 5 分钟 | 直接 API | 直接 API |
| 隐私 | ✅ 数据闭环 | 第三方 | 第三方 |

SearXNG 作为稳定底座，Tavily 作为备选——如果试用后发现 Tavily 中文也靠谱，随时切。

### 2.3 可插拔设计

LLM 和搜索都通过 Provider Protocol 抽象，切换只需改配置：

```python
# config.py
LLM_PROVIDER = "glm-4.6v"      # 改这里切模型：glm-4.6v / qwen2.5-vl / deepseek
SEARCH_BACKEND = "searxng"      # 改这里切搜索：searxng / tavily / bing
```

新增 provider 只需实现 Protocol 接口并在 gateway 注册，~60 行代码，不动任何业务逻辑。

---

## 3. 触发规则（与 V1 一致）

```
每一条消息
    ├─ 群聊 @bot     → 触发
    ├─ 私聊          → 触发
    ├─ /command      → skill 路由
    ├─ 管理员指令     → 触发
    └─ 群聊没 @      → 只存历史，不触发

会话继承：bot 回复后 10 秒内，同一发送者再发消息
（不需 @）自动继承触发状态，对话更自然。
```

---

## 4. Agent Core

### 4.1 总体流程

```
消息触发
    │
    ▼
┌──────────┐
│  Router  │  意图分类：chat / task / command / admin
└────┬─────┘
     │
     ├─ chat ──→ 直接文本回复，不进 loop
     ├─ command → skill 路由
     ├─ admin ──→ 管理指令处理
     │
     └─ task ──→ 进入 agent loop
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
   ┌────────┐ ┌────────┐ ┌──────────┐
   │Planner │→│Executor│→│Reflector │
   │任务分解│ │工具调用│ │结果评估  │
   └────────┘ └────────┘ └────┬─────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
            done            retry           replan
              │           (最多2次)      (回到Planner)
              ▼
       ┌──────────┐
       │ Builder  │  合成最终回复
       └──────────┘
```

### 4.2 Router（意图分类）

单次轻量 LLM 调用。四分类：

| 意图 | 说明 | 示例 |
|------|------|------|
| `chat` | 直接文本/多模态回复 | "你好"、"哈哈哈"、"这梗图啥意思" |
| `task` | 需要工具或多步推理 | "查天气"、"搜新闻"、"画一只猫" |
| `command` | 固定斜杠指令 | "/top"、"/memory url" |
| `admin` | 管理操作 | "/ban"、"/whitelist" |

Router system prompt 强调：**模棱两可走 `task`**——宁可多走 loop 也不漏掉需要工具的任务。

**chat 意图中如果带了图片：** GLM-4.6V 原生多模态，图片直接作为消息内容传入，无需特殊处理。LLM 天然"看见"图片并返回文本解释。

### 4.3 Planner（任务分解）

LLM 将 task 分解为步骤序列（结构化 JSON），最多 5 步。支持条件分支：

```
输入: "查今天上海天气，下雨就提醒大家带伞"

输出:
  Step 1: web_search("上海 今天 天气")
  Step 2: 条件判断
    ├─ 下雨 → Step 3: 组织群发提醒
    └─ 不下雨 → Step 3: 告知天气概况
```

超过 5 步的请求诚实告知"这个太复杂了，拆开问我吧"。

### 4.4 Executor（工具调用）

并行执行当前 step 中无依赖关系的工具调用。每个调用有 `asyncio.wait_for` 超时保护（默认 15 秒）。

### 4.5 Reflector（结果评估）

LLM 快速评估本轮执行结果：

| 结论 | 含义 |
|------|------|
| `done` | 信息完整，进入 Builder |
| `retry` | 工具返回空/异常，换方式重试（最多 2 次） |
| `replan` | 计划有问题，回到 Planner 重新分解 |

### 4.6 Builder（回复合成）

将 Plan + 执行结果 + 相关记忆合并，LLM 一次调用合成自然回复。不走循环。

### 4.7 AgentLoop 签名（预留 MessageBus 接口）

```python
class AgentLoop:
    def __init__(
        self,
        name: str,
        system_prompt: str,
        tools: list[Tool],
        llm: LLMProvider,
        bus: MessageBus | None = None,   # V2 传 None，将来升级用
    ):
        ...

    async def run(self, task: str, context: dict) -> AgentResult:
        ...

    async def _on_peer_message(self, msg: AgentMessage):
        """收到其他 agent 消息时回调。单体模式下不触发。"""
        ...
```

`bus=None` 时单体运行，零开销。将来传入 bus 实例即可参与多 agent 通信，不动 AgentLoop 核心逻辑。

---

## 5. 工具系统

### 5.1 核心通用工具（3 个）

这三个组合覆盖绝大多数场景，不提供任何专用工具：

| 工具 | 能力 | 典型调用 |
|------|------|---------|
| `web_search(query)` | 互联网搜索（后端可配置） | "今天上海天气"、"某股票股价" |
| `web_fetch(url)` | 抓取网页正文 | 打开发给 bot 的链接、搜索结果的详情页 |
| `run_code(code)` | Python 沙箱执行 | 计算、数据分析、简单图表 |

### 5.2 装饰器注册

```python
from qq_bot.tools import tool

@tool(
    name="web_search",
    description="搜索互联网获取实时信息",
    params={"query": (str, "搜索关键词")},
    category="core",
    require_auth=False,
)
async def web_search(query: str) -> str:
    ...
```

`@tool` 装饰器自动生成 OpenAI function schema 并注册到全局 registry。

不再手写 `TOOL_SCHEMAS` 和 `TOOL_HANDLERS` 两个独立 dict——新增工具只需一个装饰器函数。

### 5.3 暂时不启用的模块

- RAG 知识库（`rag/` 四件套保留代码，V2 不加载）
- 专用快捷工具（get_weather、group_stats、random_mention 等——三个通用工具已能覆盖这些场景）

---

## 6. 识图与生图

### 6.1 识图

不需要特殊触发。GLM-4.6V 是多模态模型，图片和文本一起传入消息，LLM 天然"看见"图片。

```
用户 @bot: [梗图] + "这什么意思"
  → Router: chat（理解类问题，不需要工具）
  → LLM 直接看到图片 + 文本 → 返回文字解释
  → 不走 Planner/Executor，零工具调用成本
```

关键优化：只有 @bot 或私聊时才把图片传给 LLM。群聊随便发的图不传，省 token。

### 6.2 生图

`generate_image` 是一个普通工具，LLM 自主决定是否调用：

```
用户 @bot: "帮我画一只赛博朋克风格的猫"
  → Router: task
  → Planner: generate_image(prompt="赛博朋克风格猫")
  → Executor → 外部 API 返回图片
  → Builder: "画好了！" + 图片
```

图片变换（"把这张图翻转"）：如果生图 API 支持图生图则传原图 base64，不支持则诚实告知。

---

## 7. 记忆系统

### 7.1 三层结构

| 层 | 存储 | 内容 | 生命周期 |
|------|------|------|---------|
| 工作记忆 | SQLite `sessions` | 当前会话 OpenAI 格式 messages | 保留最近 30 条 |
| 语义记忆 | ChromaDB | 从对话提取的事实片段 | 持久化，时间衰减 |
| 用户画像 | SQLite `profiles` | 结构化标签 + 统计 | 持久化 |

### 7.2 语义记忆

从对话中自动提取事实存储到 ChromaDB，检索时语义匹配 + 时间衰减：

```
记忆示例：
  "User_123456 养了一只叫咪咪的猫"
  "User_789012 喜欢讨论 Linux"
  "群里有成员约了下周六聚会"

Agent 在 Planner 阶段自动注入相关记忆。
```

### 7.3 用户画像

```sql
user_id            TEXT PRIMARY KEY,
nickname           TEXT,
traits             JSON,   -- {"interests":[...], "location":"...", ...}
first_seen         INTEGER,
last_seen          INTEGER,
interaction_count  INTEGER
```

每 10 轮对话触发一次 profile update（LLM 提取新 trait 并合并到 traits JSON）。

---

## 8. 权限控制

### 8.1 数据模型

```sql
global_blacklist   (user_id, reason, added_by, added_at)
group_whitelist    (group_id, added_by, added_at)
user_permissions   (user_id, level)   -- banned / user / admin / superuser
tool_permissions   (tool_name, min_level)
```

### 8.2 频率限制

内存 LRU 计数器：

- 每人每分钟 ≤ 10 次
- 每群每分钟 ≤ 30 次
- 管理员不限
- 超限回复"太快啦，歇一下~"并冷却 60 秒

### 8.3 管理方式

管理面板 Web 界面增删改查，或私聊 bot 用管理命令（`/ban` `/unban` `/whitelist` 等）。

---

## 9. 管理面板

基于 NoneBot2 FastAPI driver 挂载路由：

```
GET  /admin/                    → 管理面板首页 (HTML)
GET  /admin/api/chats           → 聊天记录
DELETE /admin/api/chats/:id     → 删除记录
GET  /admin/api/knowledge       → 知识库（V2 初期空，RAG 启用后有内容）
GET  /admin/api/memory/:user    → 用户画像 + 记忆
DELETE /admin/api/memory/:user/:id → 删除某条记忆
GET  /admin/api/access          → 黑白名单
POST /admin/api/access          → 添加规则
DELETE /admin/api/access/:id    → 删除规则
GET  /admin/api/config          → 当前配置
POST /admin/api/config          → 热更新配置
GET  /admin/api/logs            → agent 调用日志
```

单页 HTML 内嵌在 bot 进程。认证用 `ADMIN_TOKEN` 环境变量。

---

## 10. 定时任务

使用 `nonebot-plugin-apscheduler`，支持通过管理面板创建/暂停/删除。

```python
# 内置示例：每日早安播报
NightlySummary = ScheduledTask(
    name="morning_brief",
    trigger="cron", hour=8,
    action="agent_brief",   # 让 agent 自己搜天气+新闻+组织消息
    target_groups=["*"],
)
```

**后期加"每晚 23:00 群聊总结"示例：**

只需新增 ~30 行代码：
- `scheduler/tasks.py` 加一条 cron 回调（~10 行）
- `memory/store.py` 加 `get_today_messages(group_id)` 查询（~8 行）
- 回调中 `agent.run("总结今天的群聊内容...")` 然后 `bot.send_group_msg()`（~15 行）

不碰 AgentLoop、工具系统、权限等任何核心模块。

---

## 11. 扩展性设计

### 11.1 低难度扩展（加功能不改架构）

| 需求 | 改动 |
|------|------|
| 新增工具（如查快递） | `@tool` 装饰器一个函数，~20 行 |
| 新增 LLM provider | 实现 Protocol，注册到 gateway，~60 行 |
| 新增定时任务 | scheduler 加一条配置，~10 行 |
| 新增管理面板功能 | admin/routes.py 加一个路由，~30 行 |
| 启用 RAG | 取消注释，加载 `rag/` 模块 |
| 新增专用快捷工具 | `@tool` 装饰器，~30 行 |

### 11.2 中难度扩展（改少量核心模块）

| 需求 | 改动 |
|------|------|
| Sub-agent 升级 | 实现 Orchestrator + Aggregator，~150 行 |
| 真正多 Agent | 实现 MessageBus，agent 接入 bus，~200 行 |
| 工具执行中途人工确认 | Executor 加 HumanInTheLoop 暂停点，~80 行 |
| 跨群数据关联分析 | memory/store.py 加复杂 SQL，~50 行 |

### 11.3 高难度扩展（改骨架）

| 需求 | 为什么 |
|------|--------|
| Agent 投票/辩论共识 | 要改 AgentLoop 决策模型 |
| 实时语音 | NoneBot2 不支持，需额外协议层 |

---

## 12. V1 废弃代码清理

V2 重写后以下文件和目录直接删除：

```
删除：
  qq_bot/agent/                # 旧 ReAct loop
  qq_bot/llm/__init__.py       # 旧 adapter registry
  qq_bot/llm/base.py           # 旧 adapter base
  qq_bot/llm/deepseek.py       # DeepSeek adapter（改用 GLM-4.6V）
  qq_bot/llm/longcat.py        # LongCat adapter
  qq_bot/llm/ollama.py         # Ollama adapter
  qq_bot/plugins/chat.py       # 重写
  qq_bot/skills/               # 命令路由并入 agent
  qq_bot/security/prompt.py    # system prompt 重构
  qq_bot/security/service.py   # 注入检测改用 LLM 自身防御
  qq_bot/security/rules.py     # 废弃
  qq_bot/services/chat_history.py  # SQLite 替代
  qq_bot/services/web_search.py    # 重写（SearXNG + 可插拔后端）
  qq_bot/config/settings.py        # 精简
  data/chats/*.json                # 迁移到 SQLite 后删除

保留不动：
  qq_bot/security/preprocessor.py   # 关键词拦截
  qq_bot/security/url_validator.py  # SSRF 防护
  qq_bot/services/crawler.py        # Playwright 爬虫
  qq_bot/services/crawl_knowledge.py# 知识库爬取（RAG 启用后用到）
  qq_bot/llm/image_gen.py           # 暂时保留，以后可能替换
  qq_bot/llm/noobai_workflow.json   # 同上
  qq_bot/rag/                       # 暂时保留，V2 不加载
  qq_bot/debug_logger.py            # 调试日志
```

---

## 13. 文件结构

```
qq_bot/
├── agent/
│   ├── core.py          # AgentLoop 主状态机（self-contained）
│   ├── router.py        # 意图分类
│   ├── planner.py       # 任务分解
│   ├── executor.py      # 工具并行调用
│   ├── reflector.py     # 结果评估 + 纠错
│   ├── builder.py       # 回复合成
│   ├── state.py         # AgentState / Step / Plan
│   └── bus.py           # MessageBus（V2 不启用，接口先留好）
├── tools/
│   ├── registry.py      # @tool 装饰器 + ToolRegistry
│   └── core.py          # web_search / web_fetch / run_code
├── memory/
│   ├── manager.py       # MemoryManager 统一入口
│   ├── store.py         # SQLite 操作
│   ├── vector.py        # ChromaDB 向量存储
│   └── profile.py       # 用户画像
├── access/
│   ├── guard.py         # 权限检查 + 频率限制
│   └── models.py        # 数据模型
├── llm/
│   ├── gateway.py       # LLM Gateway
│   ├── base.py          # Provider Protocol
│   ├── glm_4v.py        # GLM-4.6V provider
│   └── image_gen.py     # (保留) 生图
├── admin/
│   ├── routes.py        # FastAPI 管理路由
│   └── templates/       # 管理面板 HTML
├── scheduler/
│   └── tasks.py         # 定时任务
├── security/            # (保留 preprocessor + url_validator)
├── rag/                 # (保留，V2 不加载)
├── services/            # (保留 crawler + crawl_knowledge)
├── config.py            # 配置
├── debug_logger.py      # (保留)
└── plugins/
    └── chat.py          # 群聊/私聊入口
```

---

## 14. 完整对话示例

### 例 1：需要工具的 task

```
群友 @bot: "帮我查今天上海天气，下雨就提醒大家带伞"

→ 触发: @bot ✅
→ Router: intent=task
→ Planner:
    Step 1: web_search("上海 今天 天气")
    Step 2: 判断天气 → 组织对应回复
→ Executor: web_search → "上海今天小雨，18-22°C"
→ Reflector: done（信息完整）
→ Builder: "今天上海小雨，18-22°C，大家出门记得带伞~"
```

### 例 2：图片理解，不下场 loop

```
群友 @bot: [发了一张梗图] + "看这个啥意思"

→ 触发: @bot ✅
→ Router: intent=chat（理解类，不需要工具）
→ GLM-4.6V 直接理解图片 + 文字 → 回复解释
→ 不走 Planner/Executor/Reflector，一次 LLM 调用搞定
```

### 例 3：会话继承

```
群友 @bot: 今天上海天气怎么样
Bot:      今天多云，20-25°C

群友:     那明天呢        ← 没 @，但在 10 秒窗口内
Bot:      明天有小雨，记得带伞~   ← bot 自动接上
```

---

## 15. 不做的事

- 不启用 RAG（代码保留，以后按需挂载）
- 不启用专用快捷工具（三个通用工具覆盖面更广）
- 不做多 agent 通信（MessageBus 接口留好但不实现）
- 不做 streaming 思考展示（V2 后期再考虑）
- 不兼容 V1 代码（干净重写）

## 16. 部署

- 开发阶段：本地电脑运行
- 正式部署：轻量云服务器（~¥50/月）Docker 部署，NapCat/LLOneBot + NoneBot2 + Agent 全在一台机器上
- 详见部署文档（后续编写）
