# QQ Bot — NoneBot2 QQ 机器人

基于 NoneBot2 的 QQ 机器人，支持群聊 @ 触发和私聊无前缀对话，接入龙猫（LongCat-Flash-Omni-2603 多模态模型）和 Pollinations（AI 生图）。

## 技术栈

| 层级 | 技术 |
|------|------|
| 消息协议 | QQ (LLOneBot / OneBot V11) |
| 核心框架 | NoneBot2 2.4.2 |
| LLM | LongCat-Flash-Omni-2603（文字+图片理解） |
| 图片生成 | Pollinations AI（免费，无需 key） |
| 联网搜索 | ddgs（DuckDuckGo 搜索） |
| 定时任务 | nonebot-plugin-apscheduler |
| 会话存储 | JSON 文件（按群/私聊分文件存储） |
| 部署 | Docker + Docker Compose |

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                         QQ 服务器                           │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ QQ 协议
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  LLOneBot（与 QQ 服务器长连接）                               │
│  - 接收消息事件（群聊/私聊/图片等）                           │
│  - 发送消息到群/私聊                                         │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP POST（反向 WS 模式）
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  NoneBot2（~fastapi 驱动，HTTP 服务器）                      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  chat        │  │  broadcast   │  │  scheduler   │      │
│  │  AI 问答     │  │  广播管理    │  │  定时推送    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  LLM ADAPTER（统一接口）                              │    │
│  │  LongCat（文字+图片理解）                            │    │
│  │  Pollinations（AI 图片生成）                         │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐    │
│  │  SEARCH（联网搜索）ddgs                              │    │
│  └──────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## 项目结构

```
qq-bot/
├── bot.py                      # NoneBot2 入口
├── .env                        # 运行时配置
├── llm_adapter/               # LLM 适配层
│   ├── __init__.py            # get_adapter() 工厂
│   ├── base.py                # BaseLLMAdapter 抽象类
│   ├── longcat.py             # 龙猫适配器（文字+图片理解）
│   ├── image_gen.py           # Pollinations 图片生成
│   └── search.py              # 联网搜索（ddgs）
├── plugins/                    # NoneBot2 插件
│   ├── chat/                  # AI 问答插件（核心）
│   │   └── __init__.py
│   ├── broadcast/              # 广播管理插件
│   │   └── __init__.py
│   └── scheduler/             # 定时任务插件
│       ├── __init__.py
│       └── sources/           # 内容源
│           ├── __init__.py
│           ├── base.py        # BaseSource 抽象类
│           ├── news.py        # 新闻源（RSS）
│           ├── weather.py     # 天气源（Open-Meteo）
│           └── custom.py      # 自定义源
├── data/                      # 数据目录
│   └── chats/                 # 聊天历史（按群/私聊分文件）
│       ├── group_{群号}.json
│       └── private_{QQ号}.json
└── tests/                     # 测试
```

## 已实现功能

### 1. 聊天（chat 插件）

**群聊：**
- 用户 @bot 触发对话
- 所有群消息被动记录到 `data/chats/group_{群号}.json`（不区分是否 @）
- 最近 10 条群聊风向作为上下文背景；个人最近 10 条（5分钟内）作为往来记录

**私聊：**
- 无需前缀，直接对话
- 存储在 `data/chats/private_{QQ号}.json`

**多模态：**
- 文字对话：LongCat-Flash-Omni-2603
- 图片理解：发送图片 + 文字描述，自动识别图片内容
- 图片生成：发送"画 xxx"指令，调用 Pollinations AI 生成图片

**LLM 调用：**
- LongCat（龙猫云端 API）
- 每个 LLM 调用注入 System Prompt，约束不暴露模型/框架信息

**身份保护（三层防御）：**
- A 层：关键词硬拦截（`"你是谁"`、`"介绍一下自己"` 等），命中直接返回"我的主人是 @1227696033"，不走 LLM
- B 层：System Prompt 软约束，不提 NoneBot/框架/模型/厂商
- C 层：Few-Shot 虚假记忆预注入，示例"我的主人是"回答模式

**Prompt 注入拦截：**
- 非超级用户触发硬标记（`[system]`、`ignore previous` 等）→ 拒绝执行
- 超级用户（SUPERUSERS）绕过检测

**联网搜索：**
- 触发词（"今天"、"天气"、"新闻"等）→ DuckDuckGo 搜索 → 结果拼入 prompt
- 默认开启（`ENABLE_WEB_SEARCH=true`）

### 2. 广播（broadcast 插件）

命令：
```
/broadcast add <群号>    # 添加广播群
/broadcast remove <群号> # 移除广播群
/broadcast list         # 查看广播群列表
/broadcast now <内容>   # 立即广播
```

定时任务按 `BROADCAST_SCHEDULE` 配置的时间（默认 8:00、12:00、18:00）推送 `BROADCAST_CONTENT_TYPES` 指定的内容源。

### 3. 定时内容（scheduler 插件）

| 内容源 | 说明 |
|--------|------|
| news | RSS 新闻（RSSHub / 联合早报） |
| weather | Open-Meteo 天气 API（免费无需 key） |
| custom | 自定义广播内容 |

新增内容源：实现 `BaseSource`，在 `sources/__init__.py` 注册即可。

## 配置说明

### .env 关键配置

```env
# === NoneBot2 ===
DRIVER=~fastapi

# === LLM Provider ===
LLM_PROVIDER=longcat
LONGCAT_API_KEY=          # 龙猫 API Key（必填，从环境变量读取）
LONGCAT_MODEL=LongCat-Flash-Omni-2603  # 多模态模型，支持图片理解

# === 图片生成（免费）===
# 无需配置 key，Pollinations 直接使用 URL 方式

# === 聊天历史 ===
HISTORY_DIR=data/chats           # 历史存储目录
GROUP_HISTORY_MAX_TURNS=300     # 每群最大消息条数

# === 联网搜索 ===
ENABLE_WEB_SEARCH=true          # true 开启

# === 超级用户 ===
SUPERUSERS=["1227696033"]       # 主人 QQ，可绕过注入检测

# === 广播 ===
BROADCAST_SCHEDULE=8:00,12:00,18:00
BROADCAST_CONTENT_TYPES=news,weather,custom
```

> **API Key 管理**：龙猫 API Key 建议通过系统环境变量设置，不写在 `.env` 文件里，以避免意外提交到代码仓库。

## LLM 适配器接口

新增 LLM 适配器需实现 `BaseLLMAdapter`：

```python
class BaseLLMAdapter(ABC):
    async def chat(
        self,
        prompt: str,
        context: list[dict] | None = None,
        *,
        system_prompt: str | None = None,
        image: bytes | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        **kwargs
    ) -> str: ...

    async def chat_stream(
        self,
        prompt: str,
        context: list[dict] | None = None,
        *,
        system_prompt: str | None = None,
        image: bytes | None = None,
    ) -> AsyncGenerator[str, None]: ...
```

注册到 `llm_adapter/__init__.py` 的 `adapters` 字典即可通过 `LLM_PROVIDER` 环境变量切换。

## 开发

### 启动

```bash
# 使用 venv 的 Python 启动（重要！）
.venv/Scripts/python.exe bot.py
```

> 注意：必须使用项目 venv 内的 Python，而非系统 Python。否则可能因包版本差异导致 ImportError。

### 测试

```bash
pytest tests/
```

## 已知问题

1. **联网搜索依赖 DuckDuckGo**：有频率限制，大规模使用建议切换至 SerpAPI
2. **消息历史无加密**：存储为明文 JSON，敏感信息勿写入聊天内容
