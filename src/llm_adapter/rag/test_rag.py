"""
RAG 测试脚本：构建索引 + 测试检索
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.chdir(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.llm_adapter.rag.retriever import build_index, Retriever


def test_rag():
    print("=== RAG 测试开始 ===\n")

    # 1. 准备测试数据
    articles = [
        {"content": "Redis 支持 RDB 和 AOF 两种持久化方式。RDB 是快照，AOF 是命令日志。生产环境建议同时开启。", "source": "redis"},
        {"content": "Python 的 asyncio 是协程并发库，用 async/await 定义协程函数。gather 可以并发执行多个协程。", "source": "python-async"},
        {"content": "Docker 容器安全：不要用 root 用户运行，使用只读文件系统，限制内存和 CPU。", "source": "docker"},
        {"content": "Git 的 rebase 可以改写提交历史，让分支更整洁。但不要在公共分支上做 rebase。", "source": "git"},
        {"content": "FastAPI 是高性能 Python Web 框架，异步是其核心特性。Uvicorn 是常用的 ASGI 服务器。", "source": "fastapi"},
        {"content": "LLM 的 prompt 优化：明确角色、分解任务、提供示例、结构化输出、限制长度。", "source": "llm"},
    ]

    print(f"1. 测试数据：{len(articles)} 篇文章")

    # 2. 尝试构建索引
    output_path = "data/test_knowledge_index"
    os.makedirs("data", exist_ok=True)

    try:
        print("\n2. 构建 FAISS 索引...")
        indexer = build_index(
            articles,
            output_path,
            index_type="flat",  # 用 flat 方便测试
            chunk_max_chars=200,
        )
        print(f"   索引构建完成，共 {indexer.chunk_count} 个 chunks")
    except ImportError as e:
        print(f"\n   依赖缺失: {e}")
        print("   需要安装: pip install sentence-transformers faiss-cpu")
        print("\n   验证文件已创建，检查代码逻辑...")
        # 验证文件存在
        from src.llm_adapter.rag import SessionChunker, Embedder, FAISSIndexer

        print(f"   - SessionChunker: OK ({SessionChunker.__module__})")
        print(f"   - Embedder: OK ({Embedder.__module__})")
        print(f"   - FAISSIndexer: OK ({FAISSIndexer.__module__})")

        print("\n   模拟分块逻辑:")
        chunker = SessionChunker(max_chars=200)
        chunks = chunker.chunk_documents(articles)
        print(f"   - 分块结果：{len(chunks)} 个 chunks")
        for i, c in enumerate(chunks):
            print(f"     [{i}] {c.content[:60]}...")
        return

    # 3. 测试检索
    if os.path.exists(f"{output_path}.index"):
        print("\n3. 测试检索...")
        retriever = Retriever(output_path, top_k=3)

        test_queries = [
            "Redis 持久化怎么配",
            "Python 异步怎么写",
            "Docker 安全要注意什么",
        ]

        for query in test_queries:
            print(f"\n   查询: {query}")
            chunks = retriever.retrieve(query)
            print(f"   结果: {len(chunks)} 条")
            for i, chunk in enumerate(chunks):
                print(f"     [{i+1}] {chunk[:80]}...")
    else:
        print("\n   索引文件不存在，跳过检索测试")

    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    test_rag()