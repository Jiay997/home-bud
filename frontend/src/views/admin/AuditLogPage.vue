<!--
  文件级注释：审计记录页（PA-09 审计留痕入口）
  - 页头卡：标题 + 脱敏说明（快照仅返回键名，正文不回传）
  - 筛选行：动作 / 对象类型（后端 action、object_type 参数过滤）
  - 表格：时间 / 操作角色 / 动作 / 对象类型 / 对象 ID / 原因 / 结果（ok/denied 着色）/ 二次确认标记
  - 分页：total + prev/pager/next（GET /admin/audit-logs，page_size≤100）
  - 快照键名行内展开展示（before_keys / after_keys，合规审阅辅助）
-->
<template>
  <div class="audit-page">
    <!-- 1. 页头卡 -->
    <section class="st-card head-card">
      <div class="head-text">
        <h2 class="head-title">审计记录</h2>
        <p class="head-sub">后台操作留痕 · 高风险操作记录二次确认与原因 · 快照仅保留键名（正文脱敏不回传）</p>
      </div>
    </section>

    <!-- 2. 筛选行卡 -->
    <section class="st-card filter-card">
      <div class="ff">
        <label>动作</label>
        <el-input v-model="filters.action" placeholder="如 risk_config_update" clearable @keyup.enter="search" />
      </div>
      <div class="ff">
        <label>对象类型</label>
        <el-input v-model="filters.object_type" placeholder="如 config_version" clearable @keyup.enter="search" />
      </div>
      <div class="ff">
        <el-button type="primary" :icon="Search" @click="search">查询</el-button>
      </div>
    </section>

    <!-- 3. 表格卡 -->
    <section class="st-card table-card">
      <el-table :data="rows" v-loading="loading" class="audit-table" row-key="id">
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="snap-wrap">
              <span class="snap-label">快照键（before）</span>
              <span class="snap-keys">{{ (row.before_keys || []).join('、') || '--' }}</span>
              <span class="snap-label">快照键（after）</span>
              <span class="snap-keys">{{ (row.after_keys || []).join('、') || '--' }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作角色" width="110">
          <template #default="{ row }">{{ roleLabel(row.operator_role) }}</template>
        </el-table-column>
        <el-table-column prop="action" label="动作" min-width="170" show-overflow-tooltip />
        <el-table-column prop="object_type" label="对象类型" width="130" show-overflow-tooltip />
        <el-table-column prop="object_id" label="对象 ID" min-width="130" show-overflow-tooltip />
        <el-table-column prop="reason" label="原因" min-width="140" show-overflow-tooltip />
        <el-table-column label="结果" width="90">
          <template #default="{ row }">
            <span class="st-tag" :class="row.result === 'denied' ? 'st-tag--red' : 'st-tag--green'">
              {{ row.result === 'denied' ? '拒绝' : '成功' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="二次确认" width="90">
          <template #default="{ row }">{{ row.confirm_used ? '已用' : '--' }}</template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
      <footer class="page-foot">
        <div class="foot-note">快照正文不回传，仅展示键名列表；展开行可查看。</div>
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          background
          @current-change="load"
        />
      </footer>
    </section>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。审计日志分页查询（筛选与分页）、快照键名展开、结果与二次确认标记。
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import { adminApi, ApiError } from '../../api/admin'

/** 审计行列表 */
const rows = ref<any[]>([])
/** 加载中 */
const loading = ref(false)
/** 当前页 */
const page = ref(1)
/** 每页条数 */
const pageSize = 20
/** 总数 */
const total = ref(0)

/** 筛选条件（动作 / 对象类型，后端参数过滤） */
const filters = reactive({ action: '', object_type: '' })

/** 角色中文映射（与后端 operator_role_snapshot 取值对齐） */
const ROLE_LABELS: Record<string, string> = {
  super_admin: '超级管理员',
  operator: '内容运营',
  support: '客服',
  expert_child: '儿童专家',
  expert_pet: '宠物专家',
}

/**
 * 函数级注释：角色代码转展示文案
 * @param role 角色代码
 * @returns 中文标签（未知值原样返回）
 */
function roleLabel(role: string): string {
  return ROLE_LABELS[role] || role || '--'
}

/**
 * 函数级注释：ISO 时间格式化（YYYY-MM-DD HH:mm:ss；空值回退 --）
 * @param iso ISO8601 字符串
 * @returns 展示时间
 */
function fmtTime(iso?: string): string {
  if (!iso) return '--'
  return String(iso).slice(0, 19).replace('T', ' ')
}

/**
 * 函数级注释：加载审计日志（按筛选条件分页查询）
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const data: any = await adminApi.auditLogList({
      action: filters.action.trim() || undefined,
      object_type: filters.object_type.trim() || undefined,
      page: page.value,
      page_size: pageSize,
    })
    rows.value = data?.items || data?.list || (Array.isArray(data) ? data : [])
    total.value = Number(data?.total ?? rows.value.length)
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '审计日志加载失败')
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

/**
 * 函数级注释：查询（重置页码后加载）
 */
function search(): void {
  page.value = 1
  load()
}

onMounted(load)
</script>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.head-card {
  padding: 20px 24px;
}

.head-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

.head-sub {
  margin-top: 2px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.filter-card {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 24px;
}

.ff {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ff label {
  font-size: var(--fs-sub);
  color: var(--ink-3);
  white-space: nowrap;
}

.ff .el-input {
  width: 220px;
}

.table-card {
  padding: 0;
  overflow: hidden;
}

.snap-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  padding: 6px 16px;
  font-size: var(--fs-caption);
}

.snap-label {
  color: var(--ink-3);
}

.snap-keys {
  color: var(--ink-2);
  font-family: var(--font-numeric);
}

.page-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 10px 24px;
  background: var(--sc-low);
  border-top: 1px solid var(--line);
}

.foot-note {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

/* 手机窄屏（375 视口）：筛选纵排全宽、分页可换行，消除横向滚动 */
@media (max-width: 640px) {
  .head-card {
    padding: 16px;
  }
  .filter-card {
    flex-wrap: wrap;
    row-gap: 10px;
    padding: 12px 16px;
  }
  .ff {
    flex: 1 1 100%;
  }
  .ff .el-input {
    flex: 1;
    width: auto;
    min-width: 0;
  }
  .page-foot {
    padding: 10px 12px;
  }
  .page-foot :deep(.el-pagination) {
    flex-wrap: wrap;
    row-gap: 6px;
    max-width: 100%;
    justify-content: center;
  }
  .page-foot :deep(.el-pager) {
    flex-wrap: wrap;
    row-gap: 6px;
    justify-content: center;
  }
  .page-foot :deep(.el-pager li) {
    margin: 0 2px;
    min-width: 30px;
  }
}
</style>
