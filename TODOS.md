# TODOS

以下改进项已在 eng review 中识别，明确推迟到 V2：

## 待办

### 1. Decorator 式 tool 注册替代手写 dict schema

- **What:** 用 `@tool(name, description)` decorator 自动生成 OpenAI function schema，替代当前 `TOOL_SCHEMAS` 列表中手写 dict 的方式
- **Why:** 当前 8 个 tool schema 是手写 dict，字段名拼写错误要运行时才发现。decorator 方式可静态校验参数类型，减少 50% 样板代码
- **Context:** 当前 tools.py 中 `TOOL_SCHEMAS` 和 `TOOL_HANDLERS` 是两个独立字典，新增工具需在两个地方同步注册，容易遗漏
- **Depends on:** 无

### 2. 流式 tool calling 支持（typing indicator）

- **What:** agent loop 支持流式输出，在 LLM 思考/调工具时向用户展示进度（如"正在搜索..."）
- **Why:** agent 多轮调用时用户需等待 3-5 秒无反馈。流式进度提示可改善体感延迟
- **Context:** DeepSeek V4 Flash 支持 streaming，当前 `chat_stream()` 已有基础。需扩展为同时流式输出 text 和 tool_calls
- **Depends on:** agent runner 需支持流式回调

### 3. 工具调用可视化调试面板

- **What:** `DEBUG_MODE=true` 时除日志外，在 bot 回复末尾附加 tool 调用摘要（如 `[调用了: search_web("天气"), get_weather("上海")]`）
- **Why:** 开发调试时需翻日志才能看到 LLM 调了哪些工具。内联摘要可即时反馈 agent 行为
- **Context:** `DEBUG_MODE` 环境变量已存在，当前只控制日志级别。可扩展为开发模式开关
- **Depends on:** 无
