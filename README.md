# QQ Bot — NoneBot2 QQ 机器人

基于 NoneBot2 的 QQ 机器人，支持群聊 @ 触发和私聊无前缀对话，接入多模型 LLM、RAG 知识库、ComfyUI 本地生图。

## 技术栈

| 层级 | 技术 |
|------|------|
| 消息协议 | QQ (LLOneBot / OneBot V11) |
| 核心框架 | NoneBot2 2.4.2 |
| LLM | LongCat-Flash-Omni-2603 / DeepSeek / Ollama |
| 图片生成 | ComfyUI + NoobAI-XL（本地部署） |
| 知识库 | bge-large-zh 向量化 + FAISS HNSW 索引 |
| 联网搜索 | DuckDuckGo |
| 会话存储 | JSON 文件（按群/私聊分文件存储） |

## 项目结构

```
qq-bot/
├── bot.py                 # NoneBot2 入口
├── qq_bot/
│   ├── config/            # 集中配置
│   ├── llm/               # LLM 适配层（LongCat / DeepSeek / Ollama / ComfyUI）
│   ├── rag/               # 知识库（分块器 + 向量化 + FAISS 索引 + 检索）
│   ├── agent/             # Agent 模块（ReAct runner / 工具注册 / 输入输出安全）
│   ├── security/          # 三层安全防御（关键词拦截 / 注入检测 / 输出脱敏 / URL 校验）
│   ├── services/          # 业务服务（聊天历史 / 网页搜索 / 爬虫）
│   ├── skills/            # Skill 命令框架（天气 / 群统计 / 随机艾特 / 网页记忆）
│   └── plugins/           # NoneBot2 插件（聊天 / 广播 / 定时）
├── data/                  # 运行时数据（不入库）
└── tests/
```

## 功能

### 聊天
- 群聊 @ 触发对话，私聊无前缀直接对话
- 全量消息监听构建群风向上下文
- 图片理解（多模态）与图片生成（ComfyUI + NoobAI-XL）
- LLM 中文提示词翻译为 Danbooru 标签提升生图质量

### RAG 知识库
- Playwright 网页爬取 → 语义边界分块 → bge-large-zh 向量化 → FAISS HNSW 索引检索
- `/memory <网址>` 在线增量索引

### 三层安全防御
- A 层：关键词硬拦截，不走 LLM
- B 层：Prompt 注入检测 + Bypass 绕过识别
- C 层：System Prompt 加固 + 输出侧正则脱敏

### Skill 命令系统
| 命令 | 功能 |
|------|------|
| `/weather <城市>` | 天气查询 |
| `/top` | 群发言排行榜 |
| `/random` | 随机艾特活跃群友 |
| `/memory <网址>` | 网页存入知识库 |

### 联网搜索
触发词匹配（"今天"、"天气"、"新闻"等）→ DuckDuckGo 搜索 → 结果拼入 prompt。

## Agent 架构

bot 已升级为 **ReAct 式 Agent**——LLM 自主决定何时调用工具、调用哪个工具、如何组合多步操作。

**工作流程：**
1. 收到 @ 或私聊消息
2. LLM 判断：直接回复 or 调用工具？
3. 调用工具 → 结果喂回 LLM → 判断是否继续
4. 最多 3 轮，输出最终回复

**可用工具（8个）：**
| 工具 | 功能 |
|------|------|
| search_web | 联网搜索 |
| get_weather | 查询天气 |
| search_knowledge | 知识库检索 |
| crawl_webpage | 爬取网页 |
| add_to_knowledge | 爬取+入库 |
| generate_image | AI 生图 |
| get_top_speakers | 群发言排行 |
| random_mention | 随机 @ |

**安全措施：**
- URL 校验防 SSRF（阻止私有 IP / 内网地址）
- Tool result 注入脱敏（过滤劫持模式 + 特殊 token）
- Per-tool `asyncio.wait_for` 超时保护
- 非工具 LLM (LongCat/Ollama) 自动降级为单次调用

**如何新增工具：**
1. 在 `qq_bot/agent/tools.py` 的 `TOOL_SCHEMAS` 列表中添加 OpenAI 兼容的 function schema
2. 在 `TOOL_HANDLERS` 字典中注册同名 handler 函数
3. handler 签名：`async def handler(params: dict, ctx: dict) -> str`

**Agent 配置（环境变量）：**
| 变量 | 默认值 | 说明 |
|------|--------|------|
| AGENT_MAX_ITER | 3 | 最大推理轮次 |
| AGENT_MAX_TOKENS | 1024 | 单次 LLM 调用最大 token |
| AGENT_TOOL_TIMEOUT | 15 | 单个工具执行超时（秒） |

## 配置

参考 `.env.example`，核心配置项：

| 变量 | 说明 |
|------|------|
| `LLM_PROVIDER` | longcat / deepseek / ollama |
| `LONGCAT_API_KEY` | 龙猫 API Key |
| `COMFYUI_BASE_URL` | ComfyUI 服务地址 |
| `ENABLE_WEB_SEARCH` | 是否开启联网搜索 |
| `SUPERUSERS` | 管理员 QQ 号列表 |
| `KNOWLEDGE_INDEX_PATH` | 知识库索引路径 |

## 启动

```bash
.venv/Scripts/python.exe bot.py
```
