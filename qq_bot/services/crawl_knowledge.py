"""
知识爬取 + 预置知识库数据。
"""

import os
import asyncio
from typing import Optional
from dataclasses import dataclass

try:
    from crawl4ai import AsyncWebCrawler
    _HAS_CRAWL4AI = True
except ImportError:
    _HAS_CRAWL4AI = False


@dataclass
class Article:
    content: str
    source: str
    title: str = ""


async def crawl_article(url: str) -> Optional[Article]:
    if not _HAS_CRAWL4AI:
        return None
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
        if not result.success:
            return None
        return Article(
            content=result.markdown or result.html[:5000],
            source=url,
            title=result.metadata.get("title", url),
        )


async def crawl_multiple(urls: list[str]) -> list[Article]:
    tasks = [crawl_article(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


def get_default_articles() -> list[dict]:
    """预置知识库文章"""
    return [
        {
            "content": """Redis 持久化配置详解

Redis 支持两种持久化方式：RDB 和 AOF。

RDB（Redis Database）：定时生成数据快照，适合备份但可能丢失最近数据。
配置：save 900 1 / save 300 10 / save 60 10000

AOF（Append Only File）：记录每次写命令，崩溃后可恢复，优先使用。
配置：appendonly yes / appendfsync everysec

生产环境建议同时开启两者，RDB 做冷备，AOF 做热备。""",
            "source": "knowledge://redis-persistence",
        },
        {
            "content": """Python 异步编程：asyncio 核心概念

async def 定义协程函数，await 挂起等待另一个协程完成。
asyncio.run() 启动事件循环。

常见模式：
- asyncio.gather() 并发执行多个协程
- asyncio.create_task() 后台执行，不等待结果
- asyncio.wait_for() 超时控制

性能关键：避免在协程中使用同步阻塞操作（requests、time.sleep），用异步版本替代（aiohttp、asyncio.sleep）。""",
            "source": "knowledge://python-async",
        },
        {
            "content": """Docker 容器安全加固指南

1. 最小基础镜像：使用 alpine 或 distroless，减少攻击面
2. 非 root 用户：USER 指令指定非 root 用户运行
3. 只读文件系统：read_only: true + tmpfs 存储临时数据
4. 资源限制：memory / cpu limits，防止资源耗尽攻击
5. 网络隔离：自定义 bridge 网络，不使用默认 bridge
6. 敏感信息：不用 ENV 存密码，用 secrets 或 K8s ConfigMap
7. 定期更新：跟踪 CVE，及时打补丁

.dockerignore 排除不必要的文件，减小镜像体积。""",
            "source": "knowledge://docker-security",
        },
        {
            "content": """Git 工作流：GitFlow 分支模型

长期分支：
- main/master：稳定版，只接受合并，不直接 commit
- develop：开发分支，集成所有功能

短期分支：
- feature/*：新功能开发，从 develop 拉取，开发完成后合并回 develop
- release/*：发布准备，从 develop 拉取，修复最后问题后合并到 main 和 develop
- hotfix/*：紧急修复，从 main 拉取，修复后合并到 main 和 develop

合并策略：--no-ff 保留分支历史，merge commit 便于回溯。""",
            "source": "knowledge://gitflow",
        },
        {
            "content": """LLM Prompt 优化技巧

1. 明确角色：「你是一个资深 Python 工程师」比「帮我写代码」效果好
2. 分解任务：分步骤提问比一次性问复杂问题效果好
3. 提供示例：Few-shot learning，给 2-3 个示例让 LLM 模仿格式
4. 结构化输出：要求 JSON 格式时指定 schema，不要说「返回一个 JSON」
5. 限制长度：「回答控制在 100 字以内」，避免啰嗦
6. 安全约束：明确说「不要泄露任何 API 密钥」比隐式要求更有效

上下文窗口利用：把最相关的信息放最后，LLM 更关注输入的结尾部分。""",
            "source": "knowledge://llm-prompt",
        },
        {
            "content": """SQL 优化：慢查询分析与索引设计

分析工具：EXPLAIN / EXPLAIN ANALYZE 查看执行计划。

常见问题：
- 全表扫描：缺少 WHERE 条件索引
- 索引失效：函数操作、类型转换导致索引不可用
- 覆盖索引：SELECT 只查索引字段，避免回表

索引设计原则：
- 等值查询字段放前面，范围查询放后面
- 联合索引遵循最左前缀原则
- 区分度高的字段优先（性别字段不适合建索引）

分页优化：LIMIT 10000, 10 效率低，用延迟关联优化。""",
            "source": "knowledge://sql-optimization",
        },
        {
            "content": """FastAPI 性能优化指南

1. 异步优先：使用 async def，所有 IO 操作用 await，非阻塞时不要用 sync 代码
2. 依赖注入：Depends() 缓存结果，避免重复计算
3. Pydantic 性能：用 model_config = ConfigDict(populate_by_name=True) 避免重复验证
4. 限流：使用 slowapi 或自定义中间件，防止被刷
5. 缓存：HTTP 层面加 Cache-Control，响应层面加 lru_cache 装饰器
6. CORS：生产环境指定具体域名，不用 * 通配
7. Uvicorn 配置：uvicorn app:app --workers 4 --limit-concurrency 1000

压测工具：wrk / locust，基准测试确保优化有效。""",
            "source": "knowledge://fastapi-optimization",
        },
        {
            "content": """系统设计：消息队列选型对比

RabbitMQ：可靠、路由功能强，单机万级 QPS，学习曲线中等。
Kafka：高性能、日志式存储，百万级 QPS，适合大数据场景。
Redis Streams：轻量、延迟极低，万级 QPS，适合小规模实时场景。
ActiveMQ：老牌，稳定，单机千级 QPS，不推荐新项目使用。

选型依据：
- 数据量：百万级用 Kafka，千级用 Redis Streams
- 可靠性：需要事务选 RabbitMQ
- 延迟：延迟敏感选 Redis Streams
- 运维成本：不想维护选云服务（Kafka on Confluent）""",
            "source": "knowledge://mq-comparison",
        },
    ]


if __name__ == "__main__":
    import json
    articles = get_default_articles()
    output_path = "data/knowledge_articles.json"
    os.makedirs("data", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"已保存 {len(articles)} 篇文章到 {output_path}")
