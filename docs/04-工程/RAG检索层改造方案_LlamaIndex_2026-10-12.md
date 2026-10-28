# 检索层换用 LlamaIndex（深度接管）+ 智谱 embedding-3（2048 维）

> **状态更新（2026-10-12）**：本方案的嵌入通道（智谱 embedding-3）、三分支降级链、retriever/kb_api 接线、脚本与测试**已全部落地生效**；其中**向量存储后端**部分（LlamaIndex PGVectorStore 自管 `data_kb_dense`）已被《[独立向量库接入方案_Milvus_2026-10-12](./独立向量库接入方案_Milvus_2026-10-12.md)》（spec: `milvus-vector-store`）接替——存储层已改原生 pymilvus + Milvus 3.0.2（**已实施**，集合 `jiaban_kb_entries`，llama-index 依赖退出）。文内 `backend/.env` 相关密钥只允许存于本地 `.env`（已 gitignore），仓库内一律占位符。

## Context

当前 RAG 检索是自研方案（`backend/app/services/retriever.py`）：字符 3-gram hashing 到 512 维稀疏向量 + 关键词双通道，pgvector 可选落位（`embedding_vec vector(512)` 原生 SQL）。语义检索质量有限，且未使用真实 Embedding 模型。

**目标**：保留 LangGraph 编排不动，检索层深度接管给 LlamaIndex：`VectorStoreIndex + PGVectorStore` 自管向量表，业务过滤改 MetadataFilters，向量模型用智谱 embedding-3（2048 维，境内已备案，符合 C-20）。`retrieve_node` 的入参/返回契约（`{"hit", "docs"}`、top8→top5、0.6 余弦 + 0.4 关键词）保持不变。

**已拍板决策**（用户确认）：
1. 仅换检索层，LangGraph 编排保留
2. 深度接管：LlamaIndex 自管向量表
3. 向量模型：智谱 BigModel embedding-3，2048 维，OpenAI 兼容端点
4. 降级链保留（spec D6）：LlamaIndex 向量检索（主）→ hashing JSONB + Python 余弦（降级，继续同步写入）→ 纯关键词
5. embedding mock 由 `EMBEDDING_PROVIDER` 显式控制（`zhipu` / `mock`），key 为空时启动告警并自动降级 mock；conftest 强制 mock 保证测试不触网

**密钥纪律**：真实 `ZHIPU_API_KEY` 只写入 `backend/.env`（已确认 gitignore），计划与仓库内一律占位符；`deploy/.env.example` 加占位。用户如有疑虑可轮换该 key。

## 已核实的关键技术事实（可直接依赖）

- llama-index-core 最新 0.14.25（Py3.12 兼容，传递依赖含 nltk/numpy/tiktoken 等，**不含 openai SDK**）；llama-index-vector-stores-postgres 0.9.0
- `PGVectorStore.from_engine(engine, ...)` 接受同步 Engine；表名 `data_{table_name}`；`perform_setup` 建扩展/表；**add 是纯追加非 upsert** → 必须「delete_nodes(kb_id 过滤) 后 add」；查询 score = `1 - cosine_distance`（即余弦相似度）
- MetadataFilters 支持 `OR`/`IS_EMPTY`/`IN`；**空值过滤仍选哨兵 `'any'`**（不依赖 JSONB NULL 语义，与 Python 回退分支完全同构）
- `VectorStoreIndex.from_vector_store(...)` + `as_retriever(similarity_top_k, filters=...)`；`BaseEmbedding` 子类只需覆写 `_get_query_embedding / _aget_query_embedding / _get_text_embedding`
- 智谱 API：`POST {base}/embeddings`，Bearer，`input` 单批 ≤64 条，`dimensions` 1-2048（embedding-3 默认 2048），响应 `data[].embedding`
- **维度坑**：pgvector 的 ivfflat/hnsw 索引对 `vector` 类型限制 2000 维，2048 维**不能建 ANN 索引** → 顺序扫描（知识库 <1 万条可接受），不传 hnsw_kwargs 即可
- 选型结论：**自定义 `BaseEmbedding` 子类 + httpx**（仿 `llm/gateway.py` 风格，可保留 mock 分支，避免 openai SDK 与默认批量 100 超智谱上限的问题）

## 文件级改动清单

### 新增
1. **`backend/app/llm/embed_client.py`**
   - `mock_embed_2048(text) -> list[float]`：3-gram MD5 折叠 % `embedding_dimensions`、权重 1+log(tf)、L2 归一化，跨进程确定性
   - `embed_texts(texts, timeout=8.0)`：provider=mock → mock；zhipu → httpx 分批（≤64），失败抛 `EmbeddingError`
2. **`backend/app/services/rag_index.py`**（唯一 LlamaIndex 触点，顶层 try-import，失败则 `available()=False`）
   - `ZhipuEmbedding(BaseEmbedding)`；`build_embed_model()`
   - `get_vector_store(create=False)`：`from_engine(get_engine(), table_name="kb_dense", embed_dim=settings.embedding_dimensions, use_jsonb=True, perform_setup=create)`，探测结果进程内缓存（仿 retriever.py:287 旧探测）
   - `build_filters(domain_alias, age_band, species) -> MetadataFilters`（哨兵语义）
   - `upsert_entry(db, kb_id)`（delete_nodes → TextNode(id_=kb_id, text=f"{title}\n{content}", metadata={kb_id, status, kb_kind, domain, age_band, species})）→ add
   - `delete_entry(kb_id)`；`sync_entry(db, kb_id)`（读 status：published 且 kb_kind∈{child,pet} → upsert，否则 delete；内部吞异常 + logger.warning，不回滚主流程）
   - `reindex_all(db)`；`query(question, domain_alias, age_band, species, top_k=8) -> list[(kb_id, cos)]`
   - 元数据空值存 `'any'`；species 仅 pet 域参与过滤
3. **`backend/scripts/reindex_rag.py`**：TRUNCATE `data_kb_dense` + 全量重新 upsert published 条目（分批），幂等，输出计数

### 修改
4. **`backend/app/services/retriever.py`**
   - `Retriever.retrieve`(:448)：改为 `rag_index.available() → _retrieve_by_index（异常则回退）→ _retrieve_fallback`
   - 新增 `_retrieve_by_index`：`rag_index.query` 得 (kb_id, cos) → 按 **kb_id** 批量取 KbEntry（旧代码 :580 用的是自增 id）→ 0.6cos+0.4kw 重排 → 有 token 过滤零分 → top5，输出契约同 `_entry_doc`(:226)
   - 删除旧路径：`PgVectorStore`(:328)、`_probe_pgvector`(:300)、`sync_embedding_vec`(:405)、`_retrieve_by_pgvector`(:542)、`densify`(:120)、`vector_literal`(:144)
   - 保留：`hashing_embed`、`cosine_sparse`、`_keyword_score`、`_score_entry`、`_entry_doc`、`_retrieve_fallback`（余弦项在降级链继续用）、`ensure_embeddings`(:592)
5. **`backend/app/core/config.py`**（命名对齐用户提供的 .env 段）
   - 新配置：`embedding_provider="zhipu"`、`zhipu_model="embedding-3"`、`zhipu_base_url="https://open.bigmodel.cn/api/paas/v4"`、`zhipu_api_key=""`、`embedding_dimensions=2048`
   - `model_whitelist`(:86-99) 追加智谱 embedding 条目（PRD NFR-1.10 供应商登记口径）
6. **`backend/app/api/v1/kb_api.py`**（状态流转同步，全部在写入后、响应前调用 `rag_index.sync_entry`，best-effort）
   - create(:322/:364-370)：删除 `sync_embedding_vec` 调用，保留 JSONB hashing 写入（降级源），改调 sync_entry
   - update(:389/:451-456)：同上
   - review pass(:528, status='published' :571)：sync_entry（→ upsert）
   - unpublish(:606)、rollback(:661)：sync_entry（→ delete）
   - submit(:479) 走 sync_entry 的 draft 分支自动 delete，无需单独逻辑
7. **`backend/scripts/init_db.py`**：`ensure_pgvector`(:88-137) 停用（旧 vector(512) DDL/回填删除），新增 `ensure_rag_index()` 调 `get_vector_store(create=True)`
8. **`backend/scripts/seed_data.py`**(:315-330)：保留 ensure_embeddings（JSONB），追加 reindex_all
9. **`backend/requirements.txt`**：`llama-index-core>=0.14,<0.15`、`llama-index-vector-stores-postgres>=0.9,<1.0`（注释：清华镜像安装）
10. **`backend/.env`**：写入真实 ZHIPU_API_KEY（唯一存放处）
11. **`deploy/.env.example`**：新增 EMBEDDING_PROVIDER/ZHIPU_MODEL/ZHIPU_BASE_URL/ZHIPU_API_KEY=(占位)/EMBEDDING_DIMENSIONS
12. **`backend/scripts/migrate_pgvector.sql`、`run_pgvector_migration.py`**：头部注释标 deprecated（文件保留）；**旧 `embedding_vec` 列不删**（回滚保险，代码停用）

## 降级/回退矩阵

| 触发条件 | 行为 |
|---|---|
| llama_index 未安装 / import 失败 | available()=False → hashing JSONB + Python 余弦回退 |
| vector 扩展或 data_kb_dense 缺失 | 同上 |
| 智谱 API 失败/超时（查询时） | `_retrieve_by_index` 捕获 → 本次回退 hashing 路径，warning |
| EMBEDDING_PROVIDER=mock / key 为空 | 查询与写入均 mock_embed_2048，全链路确定性 |
| 条目缺 JSONB embedding | 回退余弦按 0（现状 :221-222 不变） |
| 候选 0 命中 | `{"hit": False, "docs": []}` 契约不变 |

## 测试策略

- `tests/test_retriever_metrics.py`：**全保留**（纯函数未动）
- `tests/test_pgvector_store.py`：**重写** → 保留 fallback 契约用例；删 densify/SQL 组装用例；新增 monkeypatch `rag_index.query` 的混合重排 top5 用例
- `tests/conftest.py`：`_truncate_all` 追加 `data_kb_dense` 存在性 TRUNCATE；**强制 `EMBEDDING_PROVIDER=mock`**（同 REDIS_URL="" 模式）；新增 `pgvector_gated` fixture（探测扩展，缺则 skip）
- 新增 `tests/test_rag_index.py`：mock 嵌入确定性（跨进程复算/维度/‖v‖≈1）、`build_filters` 哨兵与别名语义、降级矩阵（import 缺失/扩展缺失/API 抛错）、gated 集成（真扩展下 upsert→query→delete 往返 + published/domain/age_band/species 过滤）
- E2E（SSE、llm_mock）不变——测试库无扩展自然走降级链

## 文档同步（0 待办收口，定稿前全仓 grep 旧口径）

- `docs/03-设计/DESIGN.md`：检索章节改写（LlamaIndex 架构 + 降级链）
- `docs/04-工程/宝伴-数据模型文档_V1.1.md`：T-1 维度定稿 2048（智谱 embedding-3）；HNSW 索引表述修正（2048 维无 ANN，顺序扫描）
- `deploy/README.md`(:103-113 零外部 Embedding API 叙事、:234/:237 迁移步骤、:316)：改为「主通道智谱 embedding（境内备案）+ hashing 降级」，迁移步骤换 `reindex_rag.py`
- `deploy/docker-compose.yml`(:13 注释) 同步
- 根文档《项目核心功能清单与完成度评估》(2026-10-11，内部文档，不随仓库分发)(:133/:184) 及相关报告文档 grep「零外部 Embedding API / hashing / 512」旧口径逐处更新
- `docs/02-基线/宝伴-PRD_V1.5.md` 供应商登记表：是否补录智谱（基线文档，实施前请用户确认，不擅改）

## 实施顺序（每步独立可验证）

1. 依赖安装（清华镜像）+ 更新 requirements；用最小 httpx 请求**验证智谱 key 可用**（1 条文本，2048 维返回）
2. `embed_client.py` + config 扩展 + 单测（确定性）
3. `rag_index.py` + 纯函数用例（filters/降级）
4. `retriever.py` 三分支接入、删旧路径，跑全量既有测试保绿
5. `kb_api.py` 同步链 + init_db/seed 改造 + `reindex_rag.py`
6. 本地真实链路验证（pgvector 容器）：建表 → seed → reindex → 真实检索命中
7. 测试收口（新增 test_rag_index.py、conftest、重写 test_pgvector_store.py）
8. 文档同步 + 全仓旧口径 grep + contract_check/压测复跑

## 风险与注意

- 2048 维无 ANN 索引：顺序扫描，量级受控；文档标注后续 halfvec/降维路线
- llama-index 依赖膨胀（镜像 +80~120MB）：锁定版本区间
- 索引写与业务事务不原子：best-effort + status 过滤兜底（下架内容绝不泄露）+ reindex 自愈（可挂 scheduler）
- score 语义：LlamaIndex 返回的是相似度（1-distance），勿当距离用
- 真实 key 只进 backend/.env；如 key 曾出现在公开渠道建议轮换

## 验证方案（端到端）

1. `pytest backend/tests`（含新用例）全绿
2. 本地 pgvector 库：`python scripts/init_db.py` → `python scripts/seed_data.py` → `python scripts/reindex_rag.py` → 真实问答 SSE 请求命中向量召回（对照 hashing 降级路径结果对比）
3. `python scripts/contract_check.py` 通过（前端契约不受影响）
4. `python scripts/load_test.py`（mock）复跑无回归
