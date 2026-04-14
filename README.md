# QQ Bot

基于 NoneBot2 的 QQ 群机器人，支持 AI 问答、定时广播等功能。

## 项目结构

```
qq-bot/
├── nb.toml                 # NoneBot2 项目配置
├── bot.py                  # NoneBot2 入口
├── .env.example            # 配置模板
├── llm_adapter/            # LLM 适配层
│   ├── base.py             # BaseLLMAdapter 抽象类
│   ├── ollama.py           # Ollama 适配器
│   └── deepseek.py         # DeepSeek 适配器
├── plugins/                # 插件体系
│   ├── chat/               # AI 问答
│   ├── broadcast/          # 广播管理
│   ├── scheduler/          # 定时任务
│   │   └── sources/        # 内容源
│   ├── admin/              # 管理员命令
│   └── ext/                # 扩展插件目录
└── data/                   # 数据目录
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 复制配置
cp .env.example .env
# 编辑 .env 填入真实配置

# 启动 LLOneBot（单独终端）
./LLOneBot

# 启动 NoneBot2
nb run
```

## LLM 切换

在 .env 中修改 `LLM_PROVIDER=ollama` 或 `LLM_PROVIDER=deepseek`

## 插件列表

- chat: AI 问答，@bot 触发
- broadcast: 群广播管理
- scheduler: 定时任务
- admin: 管理员命令
