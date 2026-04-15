# QQ Bot — NoneBot2 QQ 机器人

基于 NoneBot2 的 QQ 机器人，支持群聊 @ 触发和私聊无前缀对话，接入本地 Ollama（qwen2.5:7b）和云端 DeepSeek 作为 LLM。

## 技术栈

| 层级 | 技术 |
|------|------|
| 消息协议 | QQ (LLOneBot / OneBot V11) |
| 核心框架 | NoneBot2 2.4.2 |
| LLM | Ollama（本地 qwen2.5:7b）/ DeepSeek（云端） |
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
│  - 接收消息事件（群聊/私聊/入群等）                           │
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
│  │  Ollama（本地）/ DeepSeek（云端）                    │    │
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
│   ├── ollama.py              # Ollama 适配器
│   ├── deepseek.py           # DeepSeek 适配器
│   └── search.py             # 联网搜索（ddgs）
├── plugins/                   # NoneBot2 插件
│   ├── chat/                  # AI 问答插件（核心）
│   │   └── __init__.py
│   ├── broadcast/             # 广播管理插件
│   │   └── __init__.py
│   └── scheduler/             # 定时任务插件
│       ├── __init__.py
│       └── sources/            # 内容源
│           ├── __init__.py
│           ├── base.py         # BaseSource 抽象类
│           ├── news.py         # 新闻源（RSS）
│           ├── weather.py      # 天气源（Open-Meteo）
│           └── custom.py       # 自定义源
├── data/                      # 数据目录
│   └── chats/                  # 聊天历史（按群/私聊分文件）
│       ├── group_{群号}.json
│       └── private_{QQ号}.json
└── tests/                      # 测试
```

## 已实现功能

### 1. 聊天（chat 插件）

**群聊：**
- 用户 @bot 触发对话
- 所有群消息被动记录到 `data/chats/group_{群号}.json`（不区分是否 @）
- 群共享最近 300 条上下文；个人最近 15 条独立追踪

**私聊：**
- 无需前缀，直接对话
- 存储在 `data/chats/private_{QQ号}.json`

**LLM 调用：**
- Ollama（本地 qwen2.5:7b，默认）
- DeepSeek（云端，切换 `LLM_PROVIDER=deepseek`）
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
- 默认关闭（`ENABLE_WEB_SEARCH=false`）

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

# === LLM ===
LLM_PROVIDER=ollama              # ollama 或 deepseek
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT=120
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_MODEL=deepseek-chat

# === 聊天历史 ===
HISTORY_DIR=data/chats           # 历史存储目录
GROUP_HISTORY_MAX_TURNS=300     # 每群最大消息条数

# === 联网搜索 ===
ENABLE_WEB_SEARCH=false          # true 开启

# === 超级用户 ===
SUPERUSERS=["1227696033"]       # 主人 QQ，可绕过注入检测

# === 广播 ===
BROADCAST_SCHEDULE=8:00,12:00,18:00
BROADCAST_CONTENT_TYPES=news,weather,custom
```

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

注册到 `llm_adapter/__init__.py` 的 `_ADAPTERS` 字典即可通过 `LLM_PROVIDER` 环境变量切换。

## 开发

### 启动

```bash
# 启动 bot
python bot.py
```

### 测试

```bash
pytest tests/
```

## 已知问题

1. **身份保护仍有漏洞**：qwen2.5:7b 对"主人/身份"类问题有内置对齐拒绝机制，关键词拦截覆盖约 90% 场景
2. **联网搜索依赖 DuckDuckGo**：有频率限制，大规模使用建议切换至 SerpAPI
3. **消息历史无加密**：存储为明文 JSON，敏感信息勿写入聊天内容
