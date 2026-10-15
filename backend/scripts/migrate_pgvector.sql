-- =============================================================================
-- [历史回滚保留 2026-10-12] 旧 pgvector 直连路径迁移脚本
--
-- 检索主通道已为 Milvus 独立向量库（集合 jiaban_kb_entries，spec
-- milvus-vector-store），本脚本停用；文件保留仅作回滚保险：旧
-- kb_entry.embedding_vec 列**不删除**（回滚到旧代码路径时可用）。
-- 生产环境请勿再执行本脚本。
-- =============================================================================
-- 执行方式（二选一，均可重复执行 = 幂等）：
--   方式一 psql：
--     psql "postgresql://postgres:<密码>@localhost:5432/jiaban" \
--       -f backend/scripts/migrate_pgvector.sql
--     容器部署：
--     docker compose -f deploy/docker-compose.yml exec -T postgres \
--       psql -U postgres -d jiaban < backend/scripts/migrate_pgvector.sql
--   方式二 python（推荐：自动读 backend/.env 的 DATABASE_URL，含建表前置
--   与 PgVectorStore 就绪探测）：
--     cd backend
--     python scripts/run_pgvector_migration.py
--
-- 降级路径：若数据库未预装 vector 扩展（裸 postgres 镜像 / 无超级用户
-- 权限），本脚本输出 NOTICE 后整体跳过 DDL——后端检索前会探测扩展与列，
-- 不可用时自动回退进程内余弦计算路径，检索行为与降级方案一致，业务无感。
-- =============================================================================

DO $$
BEGIN
    -- 1) 扩展安装：未预装时尝试创建；失败（镜像不带 pgvector / 无权限）
    --    输出 NOTICE 后跳过全部 DDL（降级路径，不算失败）
    IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
        BEGIN
            CREATE EXTENSION IF NOT EXISTS vector;
        EXCEPTION WHEN OTHERS THEN
            RAISE NOTICE 'pgvector extension unavailable, skip migration (backend retrieval falls back to in-process): %', SQLERRM;
            RETURN;
        END;
    END IF;

    -- 2) 目标表存在性防御：kb_entry 尚未建表（迁移先于建库）时提示先建库
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_name = 'kb_entry'
    ) THEN
        RAISE NOTICE 'table kb_entry not found: run scripts/init_db.py first, then re-run this migration';
        RETURN;
    END IF;

    -- 3) 补列（幂等）：维度以代码为准（retriever.EMBED_DIM = 512）
    ALTER TABLE kb_entry ADD COLUMN IF NOT EXISTS embedding_vec vector(512);

    -- 4) 余弦距离 ivfflat 索引（检索 SQL 用 <=>；lists=100 适配中小规模知识库）
    CREATE INDEX IF NOT EXISTS idx_kb_entry_embedding_vec
        ON kb_entry USING ivfflat (embedding_vec vector_cosine_ops)
        WITH (lists = 100);

    -- 5) 列注释（幂等，重复执行覆盖同值）
    COMMENT ON COLUMN kb_entry.embedding_vec IS
        'pgvector 稠密向量（512 维，字符 3-gram hashing 稠密化；与进程内降级检索同表征空间）';
END $$;
