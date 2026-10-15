# -*- coding: utf-8 -*-
"""RAG 向量索引全量重建脚本（spec milvus-vector-store）。

对运行库执行 Milvus 向量集合全量重建：把全部 published child/pet 条目
重新向量化写入集合 jiaban_kb_entries（reindex_all 内部 drop+重建集合，
embed_client 按 EMBEDDING_PROVIDER 分发——zhipu 真实调用 / mock 确定性）。
幂等可重跑，输出写入计数；主通道不可用（pymilvus 缺失/MILVUS_URI 空/
Milvus 不可达）时输出降级说明并以退出码 1 结束。

用法（工作目录 backend/，读 .env 的 DATABASE_URL 与 MILVUS_URI）：
    python scripts/reindex_rag.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import rag_index  # noqa: E402


def main() -> int:
    """执行全量重建。

    Returns:
        0 = 重建成功；1 = 主通道不可用或执行失败。
    """
    try:
        if not rag_index.available():
            print(
                "[reindex_rag] rag index unavailable (pymilvus missing, "
                "MILVUS_URI empty or Milvus unreachable) — retrieval falls "
                "back to hashing path; nothing to rebuild."
            )
            return 1
        from app.db import get_session_factory

        db = get_session_factory()()
        try:
            written = rag_index.reindex_all(db)
            print(f"[reindex_rag] done: {written} entries written to Milvus "
                  f"collection {rag_index.COLLECTION_NAME}")
            return 0
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — 脚本顶层兜底，明确输出失败原因
        print(f"[reindex_rag] FAILED: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
