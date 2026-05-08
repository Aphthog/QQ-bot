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
│   ├── security/          # 三层安全防御（关键词拦截 / 注入检测 / 输出脱敏）
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
