<!--
  文件级注释：V3.1 危机渠道清单页（RQ-03 单一数据源，修复 N3 配置双轨）
  - 数据源单一：GET/POST/PUT /admin/channels 与问答渠道卡读同一张 crisis_channel 表；
    旧配置项 CRISIS_CHANNELS_V1 已废弃（本页顶部明示，配置页只保留跳转入口）。
  - 页头卡：标题 + 单一数据源标注 + 旧配置项废弃提示 + 刷新 + 新增渠道
  - 统计卡：总数 / 已核验 / 占位 / 待复核（summary 真实值）
  - 未达标告警条：summary.missing_required 非空时红条列出「类别 → 缺失渠道类目」
  - 渠道表：编码 / 名称 / 类目 / 号码（未回填=号码待补充，脱敏=***）/ 地域 / 服务时段 /
    状态（active 绿 / pending_review 琥珀 / placeholder 灰 / retired 描边）/ 复核到期 /
    核验人 / 适用类别 / 操作（编辑 · 核验 · 核验记录）
  - 新建对话框：编码/名称/类目/号码（可留空=占位）/地域/服务时段/适用类别/话术/排序
  - 编辑对话框：普通字段直改；**改号码**必须走二次确认块（输入渠道编码后 4 位 + 原因），
    提交携带 confirm_token（缺 confirm 后端 1602，后 4 位不符后端 1001）
  - 核验对话框：方式 / 结论 / 结论说明 / 备注 → POST /admin/channels/{code}/review
  - 核验记录抽屉：GET /admin/channels/{code}/reviews 时间线（核验人/方式/结论/时间/版本）
-->
<template>
  <div class="channel-page">
    <!-- ═══ 1. 页头卡 ═══ -->
    <section class="st-card head-card">
      <div class="head-left">
        <div class="head-text">
          <h2 class="head-title">危机渠道清单</h2>
          <p class="head-sub">
            高风险问答下发的求助渠道卡与后台维护读同一张表 · 号码未核验一律占位，不编造
          </p>
        </div>
        <div class="source-line">
          <span class="st-tag st-tag--green st-tag--plain">单一数据源 crisis_channel</span>
          <span class="st-tag st-tag--outline st-tag--plain">旧配置项 CRISIS_CHANNELS_V1 已废弃</span>
        </div>
      </div>
      <div class="head-actions">
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
        <el-button v-if="canEdit" type="primary" :icon="Plus" @click="openCreate">新增渠道</el-button>
        <span v-else class="st-tag st-tag--outline st-tag--plain">只读角色（号码脱敏）</span>
      </div>
    </section>

    <!-- ═══ 2. 统计卡 ═══ -->
    <section class="stat-grid">
      <div v-for="s in statTiles" :key="s.key" class="st-card stat-tile">
        <div class="stat-label">{{ s.label }}</div>
        <div class="stat-value numeric" :class="s.tone">{{ summary[s.key] ?? 0 }}</div>
        <div class="stat-hint">{{ s.hint }}</div>
      </div>
    </section>

    <!-- ═══ 3. 未达标类目告警条（fail-closed：缺渠道即红条，不粉饰） ═══ -->
    <el-alert
      v-if="missingList.length"
      type="error"
      :closable="false"
      show-icon
      title="必备渠道未达标（高风险类别必须同时具备对应求助渠道）"
    >
      <template #default>
        <div class="miss-list">
          <span v-for="m in missingList" :key="m.code" class="miss-item">
            <span class="miss-cat">{{ m.label }}</span>
            <span class="miss-sep">缺</span>
            <span class="miss-values">{{ m.missingText }}</span>
          </span>
        </div>
      </template>
    </el-alert>

    <!-- ═══ 4. 渠道表卡 ═══ -->
    <section class="st-card table-card">
      <el-table :data="rows" v-loading="loading" class="ch-table" row-key="channel_code">
        <el-table-column label="编码" width="150">
          <template #default="{ row }">
            <span class="numeric code-cell">{{ row.channel_code }}</span>
          </template>
        </el-table-column>
        <el-table-column label="名称" min-width="150">
          <template #default="{ row }">
            <span class="name-cell">{{ row.channel_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类目" width="120">
          <template #default="{ row }">
            <span>{{ row.category_label || categoryLabel(row.category) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="号码" width="160">
          <template #default="{ row }">
            <span v-if="row.phone_masked" class="numeric masked" title="当前角色无号码查看权限">***</span>
            <span v-else-if="row.phone_number" class="numeric phone-cell">{{ row.phone_number }}</span>
            <span v-else class="st-tag st-tag--gray st-tag--plain">号码待补充</span>
          </template>
        </el-table-column>
        <el-table-column label="地域" width="100">
          <template #default="{ row }">{{ row.region || '--' }}</template>
        </el-table-column>
        <el-table-column label="服务时段" width="130">
          <template #default="{ row }">
            <span class="muted">{{ row.service_hours || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <span class="st-tag" :class="statusTagClass(row.status)">{{ statusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="复核到期" width="140">
          <template #default="{ row }">
            <span v-if="!row.review_due_at" class="muted">--</span>
            <span v-else class="due-cell" :class="{ expired: row.expired }">
              <span class="numeric">{{ fmtTime(row.review_due_at) }}</span>
              <span v-if="row.expired" class="due-flag">已超期</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="核验人" width="120">
          <template #default="{ row }">
            <span v-if="row.verified_by">{{ row.verified_by }}</span>
            <span v-else class="muted">未核验</span>
          </template>
        </el-table-column>
        <el-table-column label="适用类别" min-width="170">
          <template #default="{ row }">
            <span v-if="row.applicable_categories?.length" class="scope-cell">
              {{ row.applicable_categories.map(riskCategoryLabel).join(' / ') }}
            </span>
            <span v-else class="muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canEdit" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canEdit" link type="primary" size="small" @click="openReview(row)">核验</el-button>
            <el-button link type="primary" size="small" @click="openReviews(row)">核验记录</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="暂无渠道条目" /></template>
      </el-table>
      <div class="table-foot">
        <span>共 {{ rows.length }} 条渠道（含占位与已停用）</span>
        <span class="numeric">data_source: {{ dataSource || 'crisis_channel' }}</span>
      </div>
    </section>

    <!-- ═══ 5. 废弃双轨提示（st-note） ═══ -->
    <footer class="st-note">
      <el-icon class="note-ico"><WarningFilled /></el-icon>
      <div>
        <strong>旧配置项 CRISIS_CHANNELS_V1 已废弃：</strong>
        渠道清单只在本页维护（crisis_channel 表）；配置页的旧 JSON 清单不再生效，也不可再编辑，
        避免问答渠道卡与后台维护出现两份不一致的数据。核验记录留痕 ≥3 年。
      </div>
    </footer>

    <!-- ═══ 6. 新建渠道对话框 ═══ -->
    <el-dialog v-model="createVisible" title="新增危机渠道" width="560px">
      <p class="dialog-tip">号码未核验时请留空，系统按占位卡下发（不编造号码）。</p>
      <el-form label-width="110px">
        <el-form-item label="渠道编码" required>
          <el-input v-model="createForm.channel_code" placeholder="如：psy_hotline_12356" maxlength="32" />
        </el-form-item>
        <el-form-item label="渠道名称" required>
          <el-input v-model="createForm.channel_name" placeholder="如：全国心理援助热线" maxlength="64" />
        </el-form-item>
        <el-form-item label="类目" required>
          <el-select v-model="createForm.category" style="width: 100%">
            <el-option v-for="(label, code) in categories" :key="code" :label="label" :value="code" />
          </el-select>
        </el-form-item>
        <el-form-item label="号码">
          <el-input v-model="createForm.phone_number" placeholder="未核验请留空" maxlength="32" />
        </el-form-item>
        <el-form-item label="覆盖地域">
          <el-input v-model="createForm.region" placeholder="如：全国" maxlength="32" />
        </el-form-item>
        <el-form-item label="服务时段">
          <el-input v-model="createForm.service_hours" placeholder="如：7×24 小时" maxlength="64" />
        </el-form-item>
        <el-form-item label="适用类别">
          <el-select v-model="createForm.applicable_categories" multiple style="width: 100%" placeholder="选择适用的风险类别">
            <el-option v-for="r in RISK_CATEGORY_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="引导话术">
          <el-input v-model="createForm.script" type="textarea" :rows="2" placeholder="渠道卡上的引导话术（可留空）" />
        </el-form-item>
        <el-form-item label="排序权重">
          <el-input-number v-model="createForm.sort_weight" :min="0" :max="9999" controls-position="right" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">新增</el-button>
      </template>
    </el-dialog>

    <!-- ═══ 7. 编辑渠道对话框（改号码二次确认） ═══ -->
    <el-dialog v-model="editVisible" :title="`编辑渠道 · ${editTarget?.channel_code || ''}`" width="600px">
      <el-form label-width="110px">
        <el-form-item label="渠道编码">
          <el-input :model-value="editTarget?.channel_code || ''" disabled />
        </el-form-item>
        <el-form-item label="渠道名称">
          <el-input v-model="editForm.channel_name" maxlength="64" />
        </el-form-item>
        <el-form-item label="类目">
          <el-select v-model="editForm.category" style="width: 100%">
            <el-option v-for="(label, code) in categories" :key="code" :label="label" :value="code" />
          </el-select>
        </el-form-item>
        <el-form-item label="号码">
          <el-input v-model="editForm.phone_number" placeholder="未回填请留空" maxlength="32" />
          <div v-if="phoneChanged" class="phone-warn">
            号码变更属高风险操作：需完成下方二次确认（后 4 位 + 原因），否则后端拒绝（1602）。
          </div>
        </el-form-item>
        <el-form-item label="覆盖地域">
          <el-input v-model="editForm.region" maxlength="32" />
        </el-form-item>
        <el-form-item label="服务时段">
          <el-input v-model="editForm.service_hours" maxlength="64" />
        </el-form-item>
        <el-form-item label="适用类别">
          <el-select v-model="editForm.applicable_categories" multiple style="width: 100%">
            <el-option v-for="r in RISK_CATEGORY_OPTIONS" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="引导话术">
          <el-input v-model="editForm.script" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="active（已核验可用）" value="active" />
            <el-option label="pending_review（待复核）" value="pending_review" />
            <el-option label="placeholder（号码待补充）" value="placeholder" />
            <el-option label="retired（已停用）" value="retired" />
          </el-select>
        </el-form-item>

        <!-- 二次确认块：仅改号码时出现 -->
        <div v-if="phoneChanged" class="confirm-box">
          <div class="confirm-head">
            <el-icon><WarningFilled /></el-icon>
            <span>改号码二次确认（必填）</span>
          </div>
          <el-form-item label="编码后 4 位" required>
            <el-input
              v-model="editForm.channel_code_suffix"
              class="numeric"
              maxlength="4"
              placeholder="请输入渠道编码后 4 位"
            />
            <div class="confirm-hint">后 4 位不符或原因为空时后端拒绝（1001），缺少确认令牌拒绝（1602）。</div>
          </el-form-item>
        </div>

        <el-form-item label="变更原因" :required="phoneChanged">
          <el-input
            v-model="editForm.reason"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
            placeholder="写入审计日志的变更原因（改号码时必填）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- ═══ 8. 核验对话框 ═══ -->
    <el-dialog v-model="reviewVisible" :title="`渠道核验 · ${reviewTarget?.channel_code || ''}`" width="520px">
      <p class="dialog-tip">
        核验结论留痕后自动顺延复核到期日；不可达/信息变更将转为待复核，号码不再对外下发。
      </p>
      <el-form label-width="100px">
        <el-form-item label="核验方式" required>
          <el-select v-model="reviewForm.review_method" style="width: 100%">
            <el-option v-for="m in REVIEW_METHODS" :key="m.value" :label="m.label" :value="m.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="核验结论" required>
          <el-select v-model="reviewForm.review_result" style="width: 100%">
            <el-option v-for="r in REVIEW_RESULTS" :key="r.value" :label="r.label" :value="r.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="结论说明">
          <el-input v-model="reviewForm.conclusion" placeholder="核验过程与结论摘要" maxlength="200" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="reviewForm.note" type="textarea" :rows="2" maxlength="300" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="reviewVisible = false">取消</el-button>
        <el-button type="primary" :loading="reviewing" @click="submitReview">提交核验</el-button>
      </template>
    </el-dialog>

    <!-- ═══ 9. 核验记录抽屉（时间线） ═══ -->
    <el-drawer v-model="recordsVisible" :title="`核验记录 · ${recordsTarget?.channel_code || ''}`" size="520px">
      <div v-loading="recordsLoading" class="timeline-wrap">
        <el-timeline v-if="records.length">
          <el-timeline-item
            v-for="r in records"
            :key="r.review_no"
            :timestamp="fmtTime(r.reviewed_at)"
            placement="top"
            :type="recordType(r.review_result)"
          >
            <div class="rec-card">
              <div class="rec-head">
                <span class="st-tag" :class="resultTagClass(r.review_result)">{{ resultLabel(r.review_result) }}</span>
                <span class="numeric rec-no">{{ r.review_no }}</span>
              </div>
              <div class="rec-meta">
                <span>方式：{{ methodLabel(r.review_method) }}</span>
                <span>核验人：{{ r.reviewer || '--' }}</span>
                <span v-if="r.channel_version">版本：{{ r.channel_version }}</span>
              </div>
              <p v-if="r.conclusion" class="rec-text">结论：{{ r.conclusion }}</p>
              <p v-if="r.note" class="rec-text muted">备注：{{ r.note }}</p>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else-if="!recordsLoading" description="暂无核验记录" :image-size="60" />
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。列表/汇总读 GET /admin/channels；写操作走
 * POST /admin/channels、PUT /admin/channels/{code}、POST /admin/channels/{code}/review；
 * 改号码必须携带 confirm_token + 渠道编码后 4 位 + 原因（后端 1602 / 1001 门控）。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Refresh, WarningFilled } from '@element-plus/icons-vue'
import {
  adminApi,
  ApiError,
  CONFIRM_TOKEN,
  getAdminInfo,
  type ChannelItem,
  type ChannelReviewRecord,
  type ChannelStatus,
  type ChannelSummary,
} from '../../api/admin'

/** 当前角色（写操作按钮按最小权限矩阵显隐；服务端 1103 仍为真边界） */
const role = String(getAdminInfo()?.role || '')
/** 是否可写渠道（channel:edit / channel:review 仅 super_admin / operator；support 只读且号码脱敏） */
const canEdit = ['super_admin', 'operator'].includes(role)

/** 渠道条目 */
const rows = ref<ChannelItem[]>([])
/** 核验汇总（缺省为空对象，避免模板取 undefined） */
const summary = ref<ChannelSummary>({
  total: 0,
  active: 0,
  placeholder: 0,
  pending_review: 0,
  retired: 0,
  verified: 0,
  by_category: {},
  missing_required: {},
})
/** 类目字典（编码 → 中文名，来自后端 categories） */
const categories = ref<Record<string, string>>({})
/** 数据源标识 */
const dataSource = ref('')
/** 列表加载中 */
const loading = ref(false)

/** 新建对话框可见性 / 提交中 */
const createVisible = ref(false)
const creating = ref(false)
/** 编辑对话框可见性 / 提交中 */
const editVisible = ref(false)
const saving = ref(false)
/** 编辑目标（原始行快照，用于判定号码是否变更） */
const editTarget = ref<ChannelItem | null>(null)
/** 核验对话框可见性 / 提交中 */
const reviewVisible = ref(false)
const reviewing = ref(false)
/** 核验目标 */
const reviewTarget = ref<ChannelItem | null>(null)
/** 核验记录抽屉可见性 / 加载中 / 记录列表 / 目标 */
const recordsVisible = ref(false)
const recordsLoading = ref(false)
const records = ref<ChannelReviewRecord[]>([])
const recordsTarget = ref<ChannelItem | null>(null)

/** 新建表单 */
const createForm = reactive({
  channel_code: '',
  channel_name: '',
  category: 'psychological',
  phone_number: '',
  region: '全国',
  service_hours: '',
  applicable_categories: [] as string[],
  script: '',
  sort_weight: 100,
})

/** 编辑表单（含二次确认字段） */
const editForm = reactive({
  channel_name: '',
  category: 'psychological',
  phone_number: '',
  region: '',
  service_hours: '',
  applicable_categories: [] as string[],
  script: '',
  status: 'active' as ChannelStatus,
  reason: '',
  channel_code_suffix: '',
})

/** 核验表单 */
const reviewForm = reactive({
  review_method: 'call_dial',
  review_result: 'reachable',
  conclusion: '',
  note: '',
})

/** 风险类别选项（与 backend channel_service.REQUIRED_CATEGORIES 键一致） */
const RISK_CATEGORY_OPTIONS = [
  { value: 'child_abuse', label: '儿童受虐' },
  { value: 'child_selfharm', label: '儿童自伤' },
  { value: 'harmful_to_minor', label: '危害未成年人' },
  { value: 'high_fever', label: '儿童急症' },
  { value: 'animal_bite', label: '动物咬伤' },
  { value: 'pet_poison', label: '宠物中毒' },
  { value: 'pet_bleeding', label: '宠物出血' },
]

/** 核验方式枚举 */
const REVIEW_METHODS = [
  { value: 'call_dial', label: '电话拨测' },
  { value: 'official_site', label: '官网核对' },
  { value: 'verbal', label: '口头确认' },
  { value: 'document', label: '书面文件' },
]

/** 核验结论枚举 */
const REVIEW_RESULTS = [
  { value: 'reachable', label: '可达（核验通过）' },
  { value: 'unreachable', label: '不可达' },
  { value: 'changed', label: '信息已变更' },
  { value: 'pending', label: '待确认' },
]

/** 统计卡定义 */
const statTiles = [
  { key: 'total' as const, label: '渠道总数', hint: '含占位与已停用', tone: '' },
  { key: 'verified' as const, label: '已核验', hint: '有号码且状态 active', tone: 'ok' },
  { key: 'placeholder' as const, label: '占位', hint: '号码待补充，不对外下发', tone: 'warn' },
  { key: 'pending_review' as const, label: '待复核', hint: '超期未复核自动降级', tone: 'warn' },
]

/**
 * 函数级注释：未达标类目清单（summary.missing_required 兼容两种形态：
 * 后端当前为 {风险类别: [缺失渠道类目]}，若后端改为字符串数组则原样展示）
 */
const missingList = computed<{ code: string; label: string; missingText: string }[]>(() => {
  const raw = summary.value?.missing_required
  const channelLabel = (code: string) => categories.value[code] || code
  if (Array.isArray(raw)) {
    return raw.length
      ? [{ code: 'all', label: '必备渠道', missingText: raw.map(channelLabel).join(' / ') }]
      : []
  }
  if (!raw || typeof raw !== 'object') return []
  return Object.entries(raw).map(([code, list]) => ({
    code,
    label: riskCategoryLabel(code),
    missingText: (Array.isArray(list) ? list : []).map(channelLabel).join(' / ') || '--',
  }))
})

/**
 * 函数级注释：编辑中号码是否已变更（变更即需二次确认）
 */
const phoneChanged = computed<boolean>(() => {
  const before = (editTarget.value?.phone_number || '').trim()
  const after = (editForm.phone_number || '').trim()
  return after !== before
})

/**
 * 函数级注释：风险类别中文名
 * @param code 风险类别编码
 * @returns 中文名（未知编码原样返回）
 */
function riskCategoryLabel(code: string): string {
  return RISK_CATEGORY_OPTIONS.find((r) => r.value === code)?.label || code || '--'
}

/**
 * 函数级注释：渠道类目中文名
 * @param code 类目编码
 * @returns 中文名（未知编码原样返回）
 */
function categoryLabel(code: string): string {
  return categories.value[code] || code || '--'
}

/**
 * 函数级注释：状态中文名
 * @param s 状态枚举
 * @returns 中文名
 */
function statusLabel(s: string): string {
  const map: Record<string, string> = {
    active: '已核验',
    pending_review: '待复核',
    placeholder: '号码待补充',
    retired: '已停用',
  }
  return map[s] || s || '--'
}

/**
 * 函数级注释：状态标签变体类（active 绿 / pending_review 琥珀 / placeholder 灰 / retired 描边）
 * @param s 状态枚举
 * @returns st-tag 修饰类
 */
function statusTagClass(s: string): string {
  if (s === 'active') return 'st-tag--green'
  if (s === 'pending_review') return 'st-tag--amber'
  if (s === 'placeholder') return 'st-tag--gray'
  return 'st-tag--outline'
}

/**
 * 函数级注释：核验方式中文名
 * @param v 方式枚举
 * @returns 中文名
 */
function methodLabel(v: string): string {
  return REVIEW_METHODS.find((m) => m.value === v)?.label || v || '--'
}

/**
 * 函数级注释：核验结论中文名
 * @param v 结论枚举
 * @returns 中文名
 */
function resultLabel(v: string): string {
  return REVIEW_RESULTS.find((r) => r.value === v)?.label || v || '--'
}

/**
 * 函数级注释：核验结论标签变体类
 * @param v 结论枚举
 * @returns st-tag 修饰类
 */
function resultTagClass(v: string): string {
  if (v === 'reachable') return 'st-tag--green'
  if (v === 'changed') return 'st-tag--amber'
  if (v === 'unreachable') return 'st-tag--red'
  return 'st-tag--gray'
}

/**
 * 函数级注释：时间线节点类型（与结论语义一致）
 * @param v 结论枚举
 * @returns el-timeline-item type
 */
function recordType(v: string): 'success' | 'warning' | 'danger' | 'primary' {
  if (v === 'reachable') return 'success'
  if (v === 'changed') return 'warning'
  if (v === 'unreachable') return 'danger'
  return 'primary'
}

/**
 * 函数级注释：ISO 时间 → YYYY-MM-DD（空值回退 --）
 * @param iso ISO8601 字符串
 * @returns 展示日期
 */
function fmtTime(iso?: string | null): string {
  if (!iso) return '--'
  return String(iso).slice(0, 10)
}

/**
 * 函数级注释：加载渠道清单与汇总
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await adminApi.channelList()
    rows.value = Array.isArray(data?.items) ? data.items : []
    if (data?.summary) summary.value = data.summary
    if (data?.categories) categories.value = data.categories
    dataSource.value = data?.data_source || ''
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '渠道清单加载失败')
    rows.value = []
  } finally {
    loading.value = false
  }
}

/**
 * 函数级注释：打开新建对话框并重置表单
 */
function openCreate(): void {
  createForm.channel_code = ''
  createForm.channel_name = ''
  createForm.category = Object.keys(categories.value)[0] || 'psychological'
  createForm.phone_number = ''
  createForm.region = '全国'
  createForm.service_hours = ''
  createForm.applicable_categories = []
  createForm.script = ''
  createForm.sort_weight = 100
  createVisible.value = true
}

/**
 * 函数级注释：提交新建（号码留空则后端落占位状态）
 */
async function submitCreate(): Promise<void> {
  if (!createForm.channel_code.trim() || !createForm.channel_name.trim()) {
    ElMessage.warning('渠道编码与名称为必填项')
    return
  }
  creating.value = true
  try {
    await adminApi.channelCreate({
      channel_code: createForm.channel_code.trim(),
      channel_name: createForm.channel_name.trim(),
      category: createForm.category,
      phone_number: createForm.phone_number.trim() || undefined,
      region: createForm.region.trim() || '全国',
      service_hours: createForm.service_hours.trim() || undefined,
      applicable_categories: createForm.applicable_categories,
      script: createForm.script.trim() || undefined,
      sort_weight: Number(createForm.sort_weight) || 100,
    })
    ElMessage.success('渠道已新增')
    createVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '新增渠道失败')
  } finally {
    creating.value = false
  }
}

/**
 * 函数级注释：打开编辑对话框
 * @param row 渠道行数据
 */
function openEdit(row: ChannelItem): void {
  editTarget.value = row
  editForm.channel_name = row.channel_name || ''
  editForm.category = row.category || 'psychological'
  editForm.phone_number = row.phone_number || ''
  editForm.region = row.region || ''
  editForm.service_hours = row.service_hours || ''
  editForm.applicable_categories = Array.isArray(row.applicable_categories)
    ? [...row.applicable_categories]
    : []
  editForm.script = row.script || ''
  editForm.status = (row.status || 'active') as ChannelStatus
  editForm.reason = ''
  editForm.channel_code_suffix = ''
  editVisible.value = true
}

/**
 * 函数级注释：提交编辑（改号码时强制二次确认：后 4 位 + 原因 + confirm_token）
 */
async function submitEdit(): Promise<void> {
  const target = editTarget.value
  if (!target) return
  const body: Record<string, any> = {
    channel_name: editForm.channel_name.trim(),
    category: editForm.category,
    region: editForm.region.trim(),
    service_hours: editForm.service_hours.trim() || undefined,
    applicable_categories: editForm.applicable_categories,
    script: editForm.script.trim() || undefined,
    status: editForm.status,
    reason: editForm.reason.trim(),
  }
  if (phoneChanged.value) {
    // 改号码：前端先做完整性校验，避免无谓请求；后端仍会独立复验（1602 / 1001）
    if (!editForm.channel_code_suffix.trim()) {
      ElMessage.warning('改号码需输入渠道编码后 4 位')
      return
    }
    if (editForm.channel_code_suffix.trim() !== (target.channel_code || '').slice(-4)) {
      ElMessage.warning('渠道编码后 4 位校验不通过')
      return
    }
    if (!editForm.reason.trim()) {
      ElMessage.warning('改号码必须填写变更原因')
      return
    }
    body.phone_number = editForm.phone_number.trim()
    body.channel_code_suffix = editForm.channel_code_suffix.trim()
    body.confirm_token = CONFIRM_TOKEN
  }
  saving.value = true
  try {
    await adminApi.channelUpdate(target.channel_code, body as any)
    ElMessage.success('渠道已保存')
    editVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '保存渠道失败')
  } finally {
    saving.value = false
  }
}

/**
 * 函数级注释：打开核验对话框
 * @param row 渠道行数据
 */
function openReview(row: ChannelItem): void {
  reviewTarget.value = row
  reviewForm.review_method = 'call_dial'
  reviewForm.review_result = 'reachable'
  reviewForm.conclusion = ''
  reviewForm.note = ''
  reviewVisible.value = true
}

/**
 * 函数级注释：提交核验记录（成功核验后后端顺延复核到期日，故刷新列表）
 */
async function submitReview(): Promise<void> {
  const target = reviewTarget.value
  if (!target) return
  reviewing.value = true
  try {
    await adminApi.channelReview(target.channel_code, {
      review_method: reviewForm.review_method as any,
      review_result: reviewForm.review_result as any,
      conclusion: reviewForm.conclusion.trim() || undefined,
      note: reviewForm.note.trim() || undefined,
    })
    ElMessage.success('核验记录已留痕')
    reviewVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '核验提交失败')
  } finally {
    reviewing.value = false
  }
}

/**
 * 函数级注释：打开核验记录抽屉并加载留痕
 * @param row 渠道行数据
 */
async function openReviews(row: ChannelItem): Promise<void> {
  recordsTarget.value = row
  records.value = []
  recordsVisible.value = true
  recordsLoading.value = true
  try {
    const data = await adminApi.channelReviews(row.channel_code)
    records.value = Array.isArray(data?.items) ? data.items : []
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '核验记录加载失败')
  } finally {
    recordsLoading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.channel-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 页头 */
.head-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
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

.head-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.source-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

/* 统计卡 */
.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.stat-tile {
  padding: 14px 16px;
}

.stat-label {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.stat-value {
  margin-top: 6px;
  font-size: 26px;
  font-weight: 600;
  line-height: 1.2;
  color: var(--ink-1);
}

.stat-value.ok {
  color: var(--accent);
}

.stat-value.warn {
  color: var(--warn);
}

.stat-hint {
  margin-top: 6px;
  font-size: 11px;
  color: var(--ink-3);
}

/* 未达标告警 */
.miss-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-top: 4px;
}

.miss-item {
  font-size: var(--fs-caption);
}

.miss-cat {
  font-weight: 600;
}

.miss-sep {
  margin: 0 6px;
  color: var(--ink-3);
}

/* 表格 */
.table-card {
  padding: var(--sp-6);
}

.code-cell {
  font-size: var(--fs-caption);
  color: var(--ink-1);
}

.name-cell {
  color: var(--ink-1);
}

.phone-cell {
  color: var(--ink-1);
}

.masked {
  letter-spacing: 2px;
  color: var(--ink-3);
}

.muted {
  color: var(--ink-3);
}

.due-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-2);
}

.due-cell.expired {
  color: var(--danger);
}

.due-flag {
  font-weight: 600;
}

.scope-cell {
  font-size: var(--fs-caption);
  color: var(--ink-2);
}

.table-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

/* 对话框 */
.dialog-tip {
  margin-bottom: 12px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.phone-warn {
  margin-top: 6px;
  font-size: var(--fs-caption);
  color: var(--warn);
  line-height: 1.6;
}

.confirm-box {
  margin: 8px 0 16px;
  padding: 12px 16px;
  border: 1px solid var(--danger);
  border-radius: var(--radius-ctl);
  background: var(--danger-soft);
}

.confirm-head {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--danger);
}

.confirm-hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--ink-3);
}

/* 核验记录时间线 */
.timeline-wrap {
  min-height: 120px;
}

.rec-card {
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface);
}

.rec-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.rec-no {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.rec-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-2);
}

.rec-text {
  margin-top: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.6;
  word-break: break-word;
}

@media (max-width: 640px) {
  .head-card {
    padding: 16px;
  }
  .head-actions {
    flex-wrap: wrap;
  }
}
</style>
