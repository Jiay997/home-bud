<!--
  文件级注释：PA-02 知识库管理列表页（Stitch 高保真形态，/admin/kb 与 /admin/dashboard）
  - 顶部页签卡：分类切换（全部/育儿/宠物/题库，计数来自真实列表统计）+ 已上架占比校准进度条 + 新建条目
  - 筛选行卡：审核状态 / 专业领域（与分类页签共用 kb_kind 状态）+ 关键词 + 搜索/重置
  - 表格卡：工具栏（条目基线 + 数据标定时间 + 区间统计）+ 表格（复选/ID/标题+领域标签/
    状态 st-tag/版本/审核人/操作按状态显隐）+ 批量操作条（批量接口未接入前置灰）+ 分页
  - 底部合规抽检提示条（st-note）；空态 el-empty
  - 审核弹窗（打分 + 二次确认 confirm_token）；下架弹窗（必填原因 + 二次确认）
-->
<template>
  <div class="kb-list-page">
    <!-- 1. 顶部页签卡 -->
    <section class="st-card head-card">
      <div class="head-main">
        <div class="kb-label">
          <el-icon :size="18"><Collection /></el-icon>
          <span>知识库：</span>
        </div>
        <!-- 分类切换按钮组（计数来自真实列表统计） -->
        <div class="kind-tabs">
          <button
            v-for="t in kindTabs"
            :key="t.value"
            type="button"
            class="kind-tab"
            :class="{ active: activeKind === t.value }"
            @click="switchKind(t.value)"
          >
            <span>{{ t.label }}</span>
            <span v-if="t.value && kindCounts[t.value] !== undefined" class="kind-count">
              {{ kindCounts[t.value] }}
            </span>
          </button>
        </div>
        <!-- 当前分类位置校准进度（真实已上架占比；无数据时隐藏） -->
        <div v-if="totalAll > 0" class="cal-line">
          <span>当前分类位置校准进度：</span>
          <div class="st-meter cal-meter">
            <div class="st-meter__fill" :style="{ width: publishedPct + '%' }"></div>
          </div>
          <span class="cal-num">{{ publishedPct }}%</span>
        </div>
      </div>
      <el-button type="primary" size="large" @click="goNew">＋ 新建条目</el-button>
    </section>

    <!-- 2. 筛选行卡 -->
    <section class="st-card filter-card">
      <div class="filter-field">
        <label class="filter-label">审核状态</label>
        <el-select v-model="filters.status" clearable placeholder="全部" class="filter-ctrl">
          <el-option v-for="(v, k) in STATUS_MAP" :key="k" :label="v.label" :value="k" />
        </el-select>
      </div>
      <!-- 专业领域：与分类页签共用 kb_kind 状态（后端现有维度） -->
      <div class="filter-field">
        <label class="filter-label">专业领域</label>
        <el-select v-model="activeKind" clearable placeholder="全部" class="filter-ctrl" @change="handleSearch">
          <el-option v-for="t in kindTabs" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </div>
      <div class="filter-field grow">
        <label class="filter-label">关键词检索</label>
        <el-input
          v-model="filters.keyword"
          placeholder="请输入标题或正文关键词"
          clearable
          :prefix-icon="Search"
          @keyup.enter="handleSearch"
        />
      </div>
      <div class="filter-actions">
        <el-button type="primary" :icon="Search" @click="handleSearch">搜索</el-button>
        <el-button @click="handleReset">重置</el-button>
      </div>
    </section>

    <!-- 3. 表格卡 -->
    <section class="st-card table-card" v-loading="loading">
      <!-- 工具栏：条目基线 + 数据标定时间 + 区间统计 -->
      <div class="table-toolbar">
        <div class="tb-left">
          <span class="baseline">
            <span class="dot"></span>
            条目基线：三审三校制
          </span>
          <span class="v-sep">|</span>
          <span v-if="lastSyncedAt">最新数据标定时间：{{ lastSyncedAt }}</span>
        </div>
        <div class="tb-right numeric">{{ rangeText }}</div>
      </div>

      <!-- 条目表格：D-14 窄屏（768）保底横向滚动，避免列被挤压/隐藏 -->
      <div class="table-scroll">
      <el-table
        ref="tableRef"
        :data="rows"
        class="kb-table"
        scrollbar-always-on
        @row-click="goEdit"
        @selection-change="onSelectionChange"
      >
        <el-table-column type="selection" width="46" />
        <el-table-column prop="kb_id" label="ID" width="110" />
        <el-table-column label="标题" min-width="220">
          <template #default="{ row }">
            <div class="title-cell" :class="{ off: row.status === 'unpublished' }">
              <span class="t">{{ row.title }}</span>
              <span v-if="kindLabel(row)" class="kind-chip" :class="{ danger: row.status === 'rejected' }">
                {{ kindLabel(row) }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="112">
          <template #default="{ row }">
            <span class="st-tag" :class="statusTagClass(row.status)">{{ statusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="80" align="center">
          <template #default="{ row }">v{{ row.version }}</template>
        </el-table-column>
        <el-table-column label="审核人" width="100">
          <template #default="{ row }">{{ row.reviewer_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click.stop="goEdit(row)">编辑</el-button>
            <el-button v-if="['draft', 'rejected'].includes(row.status)" link type="primary" size="small" @click.stop="handleSubmit(row)">
              重提
            </el-button>
            <el-button v-if="row.status === 'pending_review'" link type="warning" size="small" @click.stop="openReviewDialog(row)">
              审核
            </el-button>
            <el-button v-if="row.status === 'published'" link type="danger" size="small" @click.stop="openUnpublishDialog(row)">
              下架
            </el-button>
            <el-button v-if="row.version > 1" link type="danger" plain size="small" @click.stop="goRollback(row)">回滚</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无数据" /></template>
      </el-table>
      </div>

      <!-- 4. 批量操作条 + 分页 -->
      <div class="table-foot">
        <div class="batch-bar">
          <el-checkbox :model-value="allSelected" :disabled="!rows.length" @change="toggleAll">全选</el-checkbox>
          <el-tooltip content="批量接口待接入" placement="top">
            <span><el-button size="small" disabled>批量上架</el-button></span>
          </el-tooltip>
          <el-tooltip content="批量接口待接入" placement="top">
            <span><el-button size="small" disabled>批量下架</el-button></span>
          </el-tooltip>
          <el-tooltip content="批量接口待接入" placement="top">
            <span><el-button size="small" disabled :icon="Download">导出 CSV</el-button></span>
          </el-tooltip>
          <span v-if="selectedRows.length" class="sel-hint">已选 {{ selectedRows.length }} 条</span>
        </div>
        <el-pagination
          v-model:current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next"
          background
          @current-change="load"
        />
      </div>
    </section>

    <!-- 5. 合规抽检提示条（文案照稿） -->
    <footer class="st-note">
      <el-icon class="note-ico"><CircleCheck /></el-icon>
      <div>
        <strong>内容合规与风控基线：</strong>
        上线前 100% 双专家审核；上线后每月自动化抽检 30 条，高危类目（用药、惊厥、急性腹泻、烈性攻击）100% 专家组复核 · 合格线 ≥98%，若低于阈值将强制暂停该知识卡片输出并触发回滚报警。
      </div>
    </footer>

    <!-- 审核弹窗：打分 + 二次确认 -->
    <el-dialog v-model="reviewVisible" title="审核条目" width="480px">
      <template v-if="reviewRow">
        <p class="dialog-tip">条目：{{ reviewRow.kb_id }} {{ reviewRow.title }}</p>
        <el-form label-width="80px">
          <el-form-item label="结论">
            <el-radio-group v-model="reviewForm.verdict">
              <el-radio value="approve">通过</el-radio>
              <el-radio value="reject">驳回</el-radio>
            </el-radio-group>
          </el-form-item>
          <el-form-item v-if="reviewForm.verdict === 'approve'" label="打分">
            <el-input-number v-model="reviewForm.score" :min="0" :max="100" />
            <span class="score-tip">合格线 ≥ 98（D-05 默认值）</span>
          </el-form-item>
          <template v-else>
            <el-form-item label="驳回码">
              <el-select v-model="reviewForm.reject_code" placeholder="选择驳回原因">
                <el-option label="内容不合规" value="content_violation" />
                <el-option label="含医疗/兽药建议" value="medical_advice" />
                <el-option label="来源/版权缺失" value="source_missing" />
                <el-option label="质量不达标" value="quality_low" />
                <el-option label="其他" value="other" />
              </el-select>
            </el-form-item>
            <el-form-item label="驳回意见">
              <el-input v-model="reviewForm.comment" type="textarea" :rows="2" placeholder="写给提交人的意见（可选）" />
            </el-form-item>
          </template>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="confirmReview">提交审核结果</el-button>
      </template>
    </el-dialog>

    <!-- 下架弹窗：必填原因 -->
    <el-dialog v-model="unpublishVisible" title="下架条目" width="460px">
      <el-alert type="warning" :closable="false" title="下架后该条目立即停止参与检索与问答引用" class="dialog-alert" />
      <el-form label-width="80px" style="margin-top: 12px">
        <el-form-item label="下架原因" required>
          <el-input v-model="unpublishReason" type="textarea" :rows="3" placeholder="必填：说明下架原因，将写入审计日志" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="unpublishVisible = false">取消</el-button>
        <el-button type="danger" plain :loading="submitting" @click="confirmUnpublish">确认下架</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。列表加载/分类统计/筛选/批量勾选/审核流/下架流；
 * 危险操作均需二次确认并携带 confirm_token；批量上架/下架/导出待批量接口接入后启用。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck, Collection, Download, Search } from '@element-plus/icons-vue'
import { adminApi, ApiError, CONFIRM_TOKEN } from '../../api/admin'
import { ADMIN_ROUTE } from '../../router'

const router = useRouter()

/** 状态枚举 → 展示映射 */
const STATUS_MAP: Record<string, { label: string; type: any }> = {
  draft: { label: '草稿', type: 'info' },
  pending_review: { label: '待审核', type: 'warning' },
  published: { label: '已上架', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
  unpublished: { label: '已下架', type: 'info' },
}

/** 状态 → st-tag 变体类映射 */
const STATUS_TAG_CLASS: Record<string, string> = {
  draft: 'st-tag--outline',
  pending_review: 'st-tag--amber',
  published: 'st-tag--green',
  rejected: 'st-tag--red',
  unpublished: 'st-tag--gray',
}

/** 分类 key → 中文名（页签/标题旁领域小标签共用；value 与后端 kb_kind 枚举对齐，保留旧键兼容历史数据） */
const KIND_LABELS: Record<string, string> = {
  child: '育儿',
  pet: '宠物',
  assessment_pool: '题库',
  risk_lexicon: '风险词库',
  sensitive_lexicon: '敏感词库',
  child_care: '育儿',
  quiz: '题库',
}

/** 分类页签定义（value 与后端 kb_kind 枚举对齐；''=全部） */
const kindTabs = [
  { label: '全部', value: '' },
  { label: '育儿', value: 'child' },
  { label: '宠物', value: 'pet' },
  { label: '题库', value: 'assessment_pool' },
]

/** 当前分类页签（筛选行"专业领域"下拉共用此状态） */
const activeKind = ref('')
/** 筛选条件 */
const filters = reactive({ status: '', keyword: '' })
/** 列表数据 */
const rows = ref<any[]>([])
/** 加载中标志 */
const loading = ref(false)
/** 当前页码 */
const page = ref(1)
/** 每页条数 */
const pageSize = 20
/** 总条数 */
const total = ref(0)
/** 提交中标志（审核/下架请求防重） */
const submitting = ref(false)
/** 最近一次列表成功加载时间（工具栏"数据标定时间"展示，取自真实加载时刻） */
const lastSyncedAt = ref('')

/** 各分类条目总数（页签计数，来自真实列表统计） */
const kindCounts = reactive<Record<string, number>>({})
/** 全部条目总数（校准进度分母） */
const totalAll = ref(0)
/** 全部已上架条目数（校准进度分子） */
const publishedTotal = ref(0)

/** 已上架占比百分数（保留一位小数） */
const publishedPct = computed(() =>
  totalAll.value ? Math.round((publishedTotal.value / totalAll.value) * 1000) / 10 : 0
)

/** 当前页区间统计文案（真实分页数据） */
const rangeText = computed(() => {
  if (!total.value) return '共 0 条'
  const from = (page.value - 1) * pageSize + 1
  const to = Math.min(page.value * pageSize, total.value)
  return `显示 ${from}-${to} / ${total.value} 条`
})

/** 表格实例（全选切换用） */
const tableRef = ref()
/** 当前勾选行集合（批量操作数据源） */
const selectedRows = ref<any[]>([])
/** 是否全选（控制底部"全选"勾选态） */
const allSelected = computed(() => rows.value.length > 0 && selectedRows.value.length >= rows.value.length)

/** 审核弹窗：当前行 */
const reviewRow = ref<any>(null)
/** 审核弹窗可见性 */
const reviewVisible = ref(false)
/** 审核表单 */
const reviewForm = reactive({ verdict: 'approve', score: 98, reject_code: '', comment: '' })

/** 下架弹窗：当前行 */
const unpublishRow = ref<any>(null)
/** 下架弹窗可见性 */
const unpublishVisible = ref(false)
/** 下架原因（必填） */
const unpublishReason = ref('')

/**
 * 函数级注释：格式化当前时间为"今天 HH:mm:ss"
 * @returns 标定时间文案
 */
function fmtNow(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `今天 ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

/**
 * 函数级注释：加载条目列表（按当前分类/筛选/分页），成功后记录标定时间
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const data: any = await adminApi.kbList({
      kb_kind: activeKind.value,
      status: filters.status,
      keyword: filters.keyword,
      page: page.value,
      page_size: pageSize,
    })
    rows.value = data?.list || data?.items || data || []
    total.value = Number(data?.total ?? rows.value.length)
    lastSyncedAt.value = fmtNow()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '列表加载失败')
    rows.value = []
  } finally {
    loading.value = false
  }
}

/**
 * 函数级注释：统计各分类条目数与已上架占比（page_size=1 仅取 total，失败静默）
 * 请求：全部/育儿/宠物/题库 + 已上架（共 5 个轻量计数请求）。
 */
async function loadKindStats(): Promise<void> {
  const kinds = ['child_care', 'pet', 'quiz']
  const reqs: Promise<any>[] = [
    adminApi.kbList({ page: 1, page_size: 1 }),
    ...kinds.map((k) => adminApi.kbList({ kb_kind: k, page: 1, page_size: 1 })),
    adminApi.kbList({ status: 'published', page: 1, page_size: 1 }),
  ]
  const results = await Promise.allSettled(reqs)
  // results[0]=全部 [1..3]=各分类 [4]=已上架
  if (results[0].status === 'fulfilled') {
    totalAll.value = Number(results[0].value?.total ?? 0)
  }
  kinds.forEach((k, i) => {
    const r = results[i + 1]
    if (r.status === 'fulfilled') kindCounts[k] = Number(r.value?.total ?? 0)
  })
  if (results[4].status === 'fulfilled') {
    publishedTotal.value = Number(results[4].value?.total ?? 0)
  }
}

/**
 * 函数级注释：切换分类页签（重置页码后刷新列表）
 * @param kind 分类 key（''=全部）
 */
function switchKind(kind: string): void {
  if (activeKind.value === kind) return
  activeKind.value = kind
  handleSearch()
}

/**
 * 函数级注释：取行数据的分类中文名（无分类时返回空串，不渲染标签）
 * @param row 条目行数据
 * @returns 分类中文名
 */
function kindLabel(row: any): string {
  return KIND_LABELS[row?.kb_kind || row?.kind || ''] || ''
}

/**
 * 函数级注释：状态 → st-tag 变体类
 * @param status 条目状态枚举
 * @returns st-tag 修饰类名
 */
function statusTagClass(status: string): string {
  return STATUS_TAG_CLASS[status] || 'st-tag--gray'
}

/**
 * 函数级注释：状态 → 中文标签
 * @param status 条目状态枚举
 * @returns 状态中文名
 */
function statusLabel(status: string): string {
  return STATUS_MAP[status]?.label || status
}

/**
 * 函数级注释：搜索（重置页码后加载）
 */
function handleSearch(): void {
  page.value = 1
  load()
}

/**
 * 函数级注释：重置筛选条件（保留当前分类页签）并刷新
 */
function handleReset(): void {
  filters.status = ''
  filters.keyword = ''
  page.value = 1
  load()
}

/**
 * 函数级注释：进入新建条目编辑页
 */
function goNew(): void {
  router.push(ADMIN_ROUTE.kbNew)
}

/**
 * 函数级注释：进入编辑页（行点击或编辑按钮）
 * @param row 条目行数据
 */
function goEdit(row: any): void {
  router.push(ADMIN_ROUTE.kbEdit(row.kb_id))
}

/**
 * 函数级注释：跳转编辑页并携带回滚标记（编辑页自动打开版本历史）
 * @param row 条目行数据
 */
function goRollback(row: any): void {
  router.push({ path: ADMIN_ROUTE.kbEdit(row.kb_id), query: { rollback: '1' } })
}

/**
 * 函数级注释：表格勾选变化回调
 * @param selection 当前勾选行数组
 */
function onSelectionChange(selection: any[]): void {
  selectedRows.value = selection
}

/**
 * 函数级注释：底部"全选"切换（复用表格 toggleAllSelection 能力）
 */
function toggleAll(): void {
  tableRef.value?.toggleAllSelection()
}

/**
 * 函数级注释：提交条目进入审核流（先二次确认）
 * @param row 条目行数据
 */
async function handleSubmit(row: any): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认将条目 ${row.kb_id}「${row.title}」提交审核？`, '提交审核', { type: 'info' })
  } catch {
    return
  }
  try {
    await adminApi.kbSubmit(row.kb_id)
    ElMessage.success('已提交审核')
    load()
    loadKindStats()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '提交失败')
  }
}

/**
 * 函数级注释：打开审核弹窗（重置表单）
 * @param row 条目行数据
 */
function openReviewDialog(row: any): void {
  reviewRow.value = row
  reviewForm.verdict = 'approve'
  reviewForm.score = 98
  reviewForm.reject_code = ''
  reviewForm.comment = ''
  reviewVisible.value = true
}

/**
 * 函数级注释：提交审核结果（二次确认 → 携带 confirm_token 提交）
 */
async function confirmReview(): Promise<void> {
  if (!reviewRow.value) return
  if (reviewForm.verdict === 'reject' && !reviewForm.reject_code) {
    ElMessage.warning('请选择驳回原因')
    return
  }
  const pass = reviewForm.verdict === 'approve'
  try {
    await ElMessageBox.confirm(
      pass
        ? `确认通过并为该条目打分 ${reviewForm.score} 分？`
        : '确认驳回该条目？驳回后提交人可修改后重新提交。',
      '二次确认',
      { type: 'warning', confirmButtonText: '确认', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    await adminApi.kbReview(reviewRow.value.kb_id, {
      // 后端契约：verdict 仅接受 pass/reject；弹窗单选值为 approve/reject
      verdict: pass ? 'pass' : 'reject',
      score: pass ? reviewForm.score : undefined,
      reject_code: pass ? undefined : reviewForm.reject_code,
      comment: reviewForm.comment || undefined,
      confirm_token: CONFIRM_TOKEN,
    })
    ElMessage.success('审核结果已提交')
    reviewVisible.value = false
    load()
    loadKindStats()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '审核提交失败')
  } finally {
    submitting.value = false
  }
}

/**
 * 函数级注释：打开下架弹窗（清空原因）
 * @param row 条目行数据
 */
function openUnpublishDialog(row: any): void {
  unpublishRow.value = row
  unpublishReason.value = ''
  unpublishVisible.value = true
}

/**
 * 函数级注释：确认下架（必填原因 + 二次确认 + confirm_token）
 */
async function confirmUnpublish(): Promise<void> {
  if (!unpublishRow.value) return
  if (!unpublishReason.value.trim()) {
    ElMessage.warning('请填写下架原因（必填）')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认下架条目 ${unpublishRow.value.kb_id}？下架会触发内容追溯处置。`,
      '二次确认',
      { type: 'warning', confirmButtonText: '确认下架', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    await adminApi.kbUnpublish(unpublishRow.value.kb_id, {
      reason: unpublishReason.value.trim(),
      confirm_token: CONFIRM_TOKEN,
    })
    ElMessage.success('已下架')
    unpublishVisible.value = false
    load()
    loadKindStats()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '下架失败')
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  load()
  loadKindStats()
})
</script>

<style scoped>
/* 页面纵向排布 */
.kb-list-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ---------- 1. 顶部页签卡 ---------- */
.head-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 16px;
}

.head-main {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  min-width: 0;
}

.kb-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-1);
  font-size: var(--fs-sub);
  font-weight: 500;
  white-space: nowrap;
}

.kb-label .el-icon {
  color: var(--accent);
}

/* 分类切换按钮组 */
.kind-tabs {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
}

.kind-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-2);
  font-size: var(--fs-sub);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.kind-tab:hover:not(.active) {
  background: var(--surface);
  color: var(--ink-1);
}

/* 激活态：白底浮起 + 描边 */
.kind-tab.active {
  border-color: var(--accent-line);
  background: var(--surface);
  color: var(--accent);
  font-weight: 500;
  box-shadow: var(--shadow-e1);
}

/* 页签计数小徽章 */
.kind-count {
  padding: 0 6px;
  border-radius: var(--radius-pill);
  background: var(--surface);
  color: var(--ink-3);
  font-family: var(--font-numeric);
  font-size: var(--fs-caption);
  font-weight: 500;
  line-height: 18px;
}

.kind-tab.active .kind-count {
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
}

/* 校准进度行 */
.cal-line {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding-left: 16px;
  border-left: 1px solid var(--line);
  color: var(--ink-3);
  font-size: var(--fs-caption);
  white-space: nowrap;
}

.cal-meter {
  width: 96px;
}

.cal-num {
  color: var(--accent);
  font-family: var(--font-numeric);
  font-weight: 500;
}

/* ---------- 2. 筛选行卡 ---------- */
.filter-card {
  display: grid;
  grid-template-columns: 200px 200px 1fr auto;
  gap: 16px;
  align-items: end;
  padding: 16px;
}

.filter-label {
  display: block;
  margin-bottom: 6px;
  color: var(--ink-2);
  font-size: var(--fs-caption);
  font-weight: 500;
}

.filter-ctrl {
  width: 100%;
}

.filter-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 960px) {
  .filter-card {
    grid-template-columns: 1fr 1fr;
  }
  .filter-field.grow {
    grid-column: span 2;
  }
}

/* ---------- 3. 表格卡 ---------- */
.table-card {
  padding: 0;
  overflow: hidden;
}

/* 工具栏 */
.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 16px;
  background: var(--surface-bright);
  border-bottom: 1px solid var(--line);
  color: var(--ink-3);
  font-size: var(--fs-caption);
  flex-wrap: wrap;
}

.tb-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.baseline {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-1);
  font-weight: 500;
}

.baseline .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

.v-sep {
  color: var(--line-strong);
}

.tb-right {
  font-family: var(--font-numeric);
  white-space: nowrap;
}

/* 表格行 */
/* D-14：768 等窄屏下保底横向滚动，表格最小宽度 980px，避免列压缩隐藏 */
.table-scroll {
  width: 100%;
  overflow-x: auto;
}
.table-scroll .kb-table {
  min-width: 980px;
}
.kb-table :deep(tbody tr) {
  cursor: pointer;
}

/* 标题单元格：标题 + 领域小标签 */
.title-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.title-cell .t {
  overflow: hidden;
  color: var(--ink-1);
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 已下架行弱化 */
.title-cell.off .t {
  color: var(--ink-3);
  text-decoration: line-through;
}

.kind-chip {
  flex: none;
  padding: 0 6px;
  border-radius: 4px;
  background: var(--surface-2);
  color: var(--ink-3);
  font-size: var(--fs-caption);
  line-height: 20px;
}

/* 驳回行的领域标签转红（稿子视觉） */
.kind-chip.danger {
  background: var(--danger-soft);
  color: var(--danger);
}

/* ---------- 4. 批量操作条 + 分页 ---------- */
.table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  padding: 12px 16px;
  border-top: 1px solid var(--line);
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.sel-hint {
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

/* ---------- 弹窗 ---------- */
.dialog-tip {
  margin: 0 0 12px;
  color: var(--ink-2);
  font-size: var(--fs-sub);
}

.score-tip {
  margin-left: 10px;
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

.dialog-alert {
  margin-bottom: 4px;
}

/* 手机窄屏（375 视口）：页签/校准行换行、筛选单列，消除横向滚动 */
@media (max-width: 640px) {
  .head-card {
    padding: 12px;
  }
  .kind-tabs {
    flex-wrap: wrap;
  }
  .cal-line {
    flex-wrap: wrap;
    row-gap: 2px;
    padding-left: 0;
    border-left: none;
    white-space: normal;
  }
  .filter-card {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 12px;
  }
  .filter-field.grow {
    grid-column: span 1;
  }
  .table-foot {
    padding: 12px;
  }
  .table-foot :deep(.el-pagination) {
    flex-wrap: wrap;
    row-gap: 6px;
    max-width: 100%;
  }
  .table-foot :deep(.el-pager) {
    flex-wrap: wrap;
    row-gap: 6px;
  }
  .table-foot :deep(.el-pager li) {
    margin: 0 2px;
    min-width: 30px;
  }
}
</style>
