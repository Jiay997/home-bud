<!--
  文件级注释：V3.1 分级规则页（RQ-06 AC-RQ06-6；§7.2 发布门禁前置条件）
  - 门禁条：GET /admin/triage-rules 的 gate_ready 为 false 时红条直出「未满足」，
    列出已会签/总数（不粉饰、不降级为灰色提示）；为 true 时绿条确认。
  - 统计卡：规则总数 / 已会签 / 场景数 / 规则快照版本（snapshot 真实值）。
  - 按 scene 分组的规则表：规则号 / 标题 / 档位（红黄绿语义标签）/ 优先级 /
    月龄区间 / 状态 / 专家会签（签署人 + 时间）/ 操作（编辑 · 专家会签）。
  - 编辑对话框：level / priority / conditions（JSON 编辑器，前端先校验语法）+
    basis / observations / escalation_flags / contraindications / disclaimers 文本域 +
    status + 变更原因；提交前二次确认，请求体携带 confirm_token（缺则后端 1602）。
  - 专家会签对话框：签署人（必填）+ 备注 → POST /admin/triage-rules/{id}/review，
    成功后刷新列表与 gate_ready。
-->
<template>
  <div class="triage-page">
    <!-- ═══ 1. 页头卡 ═══ -->
    <section class="st-card head-card">
      <div class="head-text">
        <h2 class="head-title">分级规则（红 / 黄 / 绿档位）</h2>
        <p class="head-sub">
          条目化分级决策规则 · 阈值与档位由服务端引擎执行 · 变更留痕并受专家会签门禁约束
        </p>
        <div class="head-meta">
          <span class="st-tag st-tag--outline st-tag--plain">
            规则快照版本 {{ snapshot.rule_version ?? '--' }}
          </span>
          <span class="st-tag st-tag--outline st-tag--plain">
            快照来源 {{ snapshot.source ?? '--' }}
          </span>
        </div>
      </div>
      <div class="head-actions">
        <el-button :icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </section>

    <!-- ═══ 2. 发布门禁条（未全部会签时红条直出） ═══ -->
    <el-alert
      v-if="loaded && !gateReady"
      type="error"
      :closable="false"
      show-icon
      title="发布门禁未满足：分级决策规则尚未完成专家书面会签"
    >
      <template #default>
        <div class="gate-detail">
          当前已会签 <strong class="numeric">{{ signed }}</strong> /
          <strong class="numeric">{{ total }}</strong> 条；
          未完成会签前，本批规则不满足 V3.1 上线评审门禁（E2E-19），不得对外发布档位结论。
        </div>
      </template>
    </el-alert>
    <div v-else-if="loaded && gateReady" class="st-card gate-ok">
      <span class="st-tag st-tag--green">门禁满足</span>
      <span class="gate-ok-text">
        全部 {{ total }} 条规则已完成专家会签（{{ signed }}/{{ total }}），满足上线评审门禁。
      </span>
    </div>

    <!-- ═══ 3. 统计卡 ═══ -->
    <section class="stat-grid">
      <div class="st-card stat-tile">
        <div class="stat-label">规则总数</div>
        <div class="stat-value numeric">{{ total }}</div>
        <div class="stat-hint">按场景分组维护</div>
      </div>
      <div class="st-card stat-tile">
        <div class="stat-label">已会签</div>
        <div class="stat-value numeric" :class="gateReady ? 'ok' : 'warn'">{{ signed }}</div>
        <div class="stat-hint">专家书面签署并留痕</div>
      </div>
      <div class="st-card stat-tile">
        <div class="stat-label">场景数</div>
        <div class="stat-value numeric">{{ groups.length }}</div>
        <div class="stat-hint">发热 / 呕吐腹泻 / 外伤 / 误食 / 宠物急症</div>
      </div>
      <div class="st-card stat-tile">
        <div class="stat-label">未会签</div>
        <div class="stat-value numeric" :class="unsignedCount ? 'warn' : ''">{{ unsignedCount }}</div>
        <div class="stat-hint">红档规则未会签即阻塞发布</div>
      </div>
    </section>

    <!-- ═══ 4. 筛选行 ═══ -->
    <section class="st-card filter-card">
      <span class="f-label">场景</span>
      <el-select v-model="sceneFilter" class="f-ctrl" placeholder="全部场景">
        <el-option label="全部场景" value="" />
        <el-option v-for="(label, code) in SCENE_LABELS" :key="code" :label="label" :value="code" />
      </el-select>
      <span class="f-hint">仅影响列表展示，规则与门禁状态不随筛选变化</span>
    </section>

    <!-- ═══ 5. 按场景分组的规则表 ═══ -->
    <section v-for="g in visibleGroups" :key="g.scene" class="st-card scene-card">
      <div class="scene-head">
        <div class="st-section-head">{{ g.label }}</div>
        <div class="scene-meta">
          <span class="numeric">共 {{ g.items.length }} 条</span>
          <span class="v-sep">·</span>
          <span class="numeric" :class="{ warn: g.signed < g.items.length }">
            已会签 {{ g.signed }}/{{ g.items.length }}
          </span>
        </div>
      </div>
      <el-table :data="g.items" size="small" class="triage-table">
        <el-table-column label="规则号" width="150">
          <template #default="{ row }">
            <span class="numeric rule-id">{{ row.rule_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="200">
          <template #default="{ row }">
            <span class="rule-title">{{ row.title || '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="档位" width="110">
          <template #default="{ row }">
            <span class="st-tag" :class="levelTagClass(row.level)">{{ levelLabel(row.level) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <span class="numeric">{{ row.priority ?? '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="月龄区间" width="130">
          <template #default="{ row }">
            <span class="numeric age-cell">{{ fmtAge(row.age_min_months, row.age_max_months) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="st-tag st-tag--plain" :class="row.status === 'active' ? 'st-tag--green' : 'st-tag--gray'">
              {{ row.status === 'active' ? '生效' : row.status || '--' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="专家会签" min-width="180">
          <template #default="{ row }">
            <span v-if="row.expert_signoff" class="signoff-cell">
              <span class="st-tag st-tag--green st-tag--plain">已会签</span>
              <span class="signoff-name">{{ row.expert_signoff }}</span>
              <span class="signoff-time numeric">{{ fmtTime(row.expert_reviewed_at) }}</span>
            </span>
            <span v-else class="st-tag st-tag--red st-tag--plain">未会签</span>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="80">
          <template #default="{ row }">
            <span class="numeric muted">v{{ row.version ?? '--' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canEditRule" link type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canSignoff" link type="primary" size="small" @click="openSignoff(row)">专家会签</el-button>
            <span v-if="!canEditRule && !canSignoff" class="muted">只读</span>
          </template>
        </el-table-column>
        <template #empty><el-empty description="该场景暂无规则" :image-size="60" /></template>
      </el-table>
    </section>

    <el-empty v-if="loaded && !groups.length" description="暂无分级规则" />

    <!-- ═══ 6. 底部提示 ═══ -->
    <footer class="st-note warn-note">
      <el-icon class="note-ico"><WarningFilled /></el-icon>
      <div>
        <strong>阈值口径：</strong>
        档位判定由服务端规则引擎执行，模型不得改写档位；阈值变更需二次确认并写入审计日志，
        变更后规则快照 60 秒内生效。未完成专家会签的规则不得作为发布依据。
      </div>
    </footer>

    <!-- ═══ 7. 编辑规则对话框 ═══ -->
    <el-dialog v-model="editVisible" :title="`编辑分级规则 · ${editTarget?.rule_id || ''}`" width="680px">
      <el-form label-width="120px">
        <el-form-item label="规则号">
          <el-input :model-value="editTarget?.rule_id || ''" disabled />
        </el-form-item>
        <el-form-item label="标题">
          <el-input v-model="editForm.title" maxlength="128" />
        </el-form-item>
        <el-form-item label="档位">
          <el-select v-model="editForm.level" style="width: 100%">
            <el-option label="red（建议立即就医）" value="red" />
            <el-option label="yellow（建议尽快评估）" value="yellow" />
            <el-option label="green（可居家观察）" value="green" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="editForm.priority" :min="0" :max="9999" controls-position="right" />
          <span class="field-hint">数值大者优先匹配</span>
        </el-form-item>
        <el-form-item label="条件（JSON）">
          <el-input
            v-model="editForm.conditions"
            type="textarea"
            :rows="6"
            class="json-input"
            placeholder='{"any_keywords":["..."],"temp_min":39,"duration_min_hours":24}'
          />
          <div class="field-hint">
            支持 any_keywords / all_keywords / none_keywords / temp_min / temp_max /
            duration_min_hours / mental_state；语法错误将在此处拦截，不提交。
          </div>
          <div v-if="jsonError" class="json-error">{{ jsonError }}</div>
        </el-form-item>
        <el-form-item label="循证依据">
          <el-input v-model="editForm.basis" type="textarea" :rows="2" maxlength="500" />
        </el-form-item>
        <el-form-item label="观察项">
          <el-input
            v-model="editForm.observations"
            type="textarea"
            :rows="3"
            placeholder="每行一条观察项"
          />
        </el-form-item>
        <el-form-item label="升级红旗">
          <el-input
            v-model="editForm.escalation_flags"
            type="textarea"
            :rows="2"
            placeholder="每行一条升级红旗（出现任一项即升级处理）"
          />
        </el-form-item>
        <el-form-item label="禁忌说明">
          <el-input v-model="editForm.contraindications" type="textarea" :rows="2" placeholder="每行一条" />
        </el-form-item>
        <el-form-item label="免责声明">
          <el-input v-model="editForm.disclaimers" type="textarea" :rows="2" placeholder="每行一条" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="active（生效）" value="active" />
            <el-option label="inactive（停用）" value="inactive" />
            <el-option label="draft（草稿）" value="draft" />
          </el-select>
        </el-form-item>
        <el-form-item label="变更原因" required>
          <el-input
            v-model="editForm.reason"
            type="textarea"
            :rows="2"
            maxlength="200"
            show-word-limit
            placeholder="写入审计日志的变更原因（必填）"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitEdit">保存（二次确认）</el-button>
      </template>
    </el-dialog>

    <!-- ═══ 8. 专家会签对话框 ═══ -->
    <el-dialog v-model="signoffVisible" :title="`专家会签 · ${signoffTarget?.rule_id || ''}`" width="520px">
      <p class="dialog-tip">
        会签为发布门禁前置条件：签署后本规则记为已确认，签署人与时间写入审计日志。
      </p>
      <el-form label-width="100px">
        <el-form-item label="规则标题">
          <span class="signoff-title">{{ signoffTarget?.title || '--' }}</span>
        </el-form-item>
        <el-form-item label="档位">
          <span class="st-tag" :class="levelTagClass(signoffTarget?.level || '')">
            {{ levelLabel(signoffTarget?.level || '') }}
          </span>
        </el-form-item>
        <el-form-item label="签署人" required>
          <el-input v-model="signoffForm.expert_signoff" placeholder="姓名 / 工号" maxlength="64" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="signoffForm.note" type="textarea" :rows="3" maxlength="300" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="signoffVisible = false">取消</el-button>
        <el-button type="primary" :loading="signing" @click="submitSignoff">确认会签</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。列表读 GET /admin/triage-rules（含 snapshot 与 gate_ready）；
 * 编辑走 PUT /admin/triage-rules/{rule_id}（必须 confirm_token + reason）；
 * 会签走 POST /admin/triage-rules/{rule_id}/review。
 */
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, WarningFilled } from '@element-plus/icons-vue'
import {
  adminApi,
  ApiError,
  CONFIRM_TOKEN,
  getAdminInfo,
  type TriageRuleItem,
  type TriageSnapshot,
} from '../../api/admin'

/** 当前角色（按最小权限矩阵显隐操作入口；服务端 1103 仍为真边界） */
const role = String(getAdminInfo()?.role || '')
/** 可编辑规则：triage:edit 仅 super_admin / operator */
const canEditRule = ['super_admin', 'operator'].includes(role)
/** 可会签：triage:review 为 super_admin 与育儿/宠物专家（operator 无此权限） */
const canSignoff = ['super_admin', 'expert_child', 'expert_pet'].includes(role)

/** 规则列表 */
const rules = ref<TriageRuleItem[]>([])
/** 规则快照摘要 */
const snapshot = ref<TriageSnapshot>({})
/** 已会签条数 */
const signed = ref(0)
/** 规则总数 */
const total = ref(0)
/** 门禁是否满足（全部会签） */
const gateReady = ref(false)
/** 列表加载中 / 首次加载完成 */
const loading = ref(false)
const loaded = ref(false)
/** 场景筛选 */
const sceneFilter = ref('')

/** 编辑对话框 */
const editVisible = ref(false)
const saving = ref(false)
const editTarget = ref<TriageRuleItem | null>(null)
/** 条件 JSON 语法错误提示（空串表示无错误） */
const jsonError = ref('')

/** 会签对话框 */
const signoffVisible = ref(false)
const signing = ref(false)
const signoffTarget = ref<TriageRuleItem | null>(null)

/** 场景中文名（与 backend app/triage/templates.py 场景键一致） */
const SCENE_LABELS: Record<string, string> = {
  fever: '发热（婴幼儿发热分月龄）',
  vomit: '呕吐腹泻',
  trauma: '外伤',
  ingestion: '误食',
  pet_acute: '宠物急症',
}

/** 编辑表单（数组字段用「每行一条」文本域编辑，提交时按行切分） */
const editForm = reactive({
  title: '',
  level: 'yellow',
  priority: 100,
  conditions: '{}',
  basis: '',
  observations: '',
  escalation_flags: '',
  contraindications: '',
  disclaimers: '',
  status: 'active',
  reason: '',
})

/** 会签表单 */
const signoffForm = reactive({ expert_signoff: '', note: '' })

/**
 * 函数级注释：按场景分组的规则（组内按优先级倒序）
 */
const groups = computed(() => {
  const map = new Map<string, TriageRuleItem[]>()
  for (const rule of rules.value) {
    const key = rule.scene || 'unknown'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(rule)
  }
  const ORDER = ['pet_acute', 'fever', 'vomit', 'trauma', 'ingestion']
  return [...map.entries()]
    .map(([scene, items]) => ({
      scene,
      label: SCENE_LABELS[scene] || scene,
      items: items.slice().sort((a, b) => Number(b.priority || 0) - Number(a.priority || 0)),
      signed: items.filter((r) => !!r.expert_signoff).length,
    }))
    .sort((a, b) => {
      const ia = ORDER.indexOf(a.scene)
      const ib = ORDER.indexOf(b.scene)
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
    })
})

/** 场景筛选后的分组 */
const visibleGroups = computed(() =>
  sceneFilter.value ? groups.value.filter((g) => g.scene === sceneFilter.value) : groups.value
)

/** 未会签条数 */
const unsignedCount = computed(() => Math.max(0, total.value - signed.value))

/**
 * 函数级注释：档位中文名
 * @param level red / yellow / green
 * @returns 中文档位
 */
function levelLabel(level: string): string {
  if (level === 'red') return '红档 · 立即就医'
  if (level === 'yellow') return '黄档 · 尽快评估'
  if (level === 'green') return '绿档 · 居家观察'
  return level || '--'
}

/**
 * 函数级注释：档位标签变体类（红/黄/绿语义色）
 * @param level red / yellow / green
 * @returns st-tag 修饰类
 */
function levelTagClass(level: string): string {
  if (level === 'red') return 'st-tag--red'
  if (level === 'yellow') return 'st-tag--amber'
  if (level === 'green') return 'st-tag--green'
  return 'st-tag--gray'
}

/**
 * 函数级注释：月龄区间格式化
 * @param min 起始月龄（可空）
 * @param max 结束月龄（可空，null 表示无上限）
 * @returns 区间文案
 */
function fmtAge(min?: number | null, max?: number | null): string {
  const hasMin = min !== null && min !== undefined
  const hasMax = max !== null && max !== undefined
  if (hasMin && hasMax) return `${min}–${max} 月龄`
  if (hasMin) return `≥ ${min} 月龄`
  if (hasMax) return `≤ ${max} 月龄`
  return '全月龄'
}

/**
 * 函数级注释：时间格式化（ISO → YYYY-MM-DD HH:mm；空值回退 --）
 * @param iso ISO8601 字符串
 * @returns 展示时间
 */
function fmtTime(iso?: string | null): string {
  if (!iso) return '--'
  return String(iso).slice(0, 16).replace('T', ' ')
}

/**
 * 函数级注释：数组字段 ↔ 多行文本
 * @param list 字符串数组
 * @returns 每行一条的文本
 */
function linesOf(list?: string[] | null): string {
  return Array.isArray(list) ? list.join('\n') : ''
}

/**
 * 函数级注释：多行文本 → 数组（去空行与首尾空格）
 * @param text 多行文本
 * @returns 字符串数组
 */
function arrOf(text: string): string[] {
  return String(text || '')
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean)
}

/**
 * 函数级注释：加载规则列表（含门禁状态）
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const data = await adminApi.triageRuleList()
    rules.value = Array.isArray(data?.items) ? data.items : []
    snapshot.value = data?.snapshot || {}
    signed.value = Number(data?.signed || 0)
    total.value = Number(data?.total ?? rules.value.length)
    gateReady.value = !!data?.gate_ready
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '分级规则加载失败')
    rules.value = []
  } finally {
    loading.value = false
    loaded.value = true
  }
}

/**
 * 函数级注释：打开编辑对话框并回填当前规则
 * @param row 规则行数据
 */
function openEdit(row: TriageRuleItem): void {
  editTarget.value = row
  editForm.title = row.title || ''
  editForm.level = row.level || 'yellow'
  editForm.priority = Number(row.priority ?? 100)
  editForm.conditions = JSON.stringify(row.conditions || {}, null, 2)
  editForm.basis = row.basis || ''
  editForm.observations = linesOf(row.observations)
  editForm.escalation_flags = linesOf(row.escalation_flags)
  editForm.contraindications = linesOf(row.contraindications)
  editForm.disclaimers = linesOf(row.disclaimers)
  editForm.status = row.status || 'active'
  editForm.reason = ''
  jsonError.value = ''
  editVisible.value = true
}

/**
 * 函数级注释：提交编辑（JSON 语法校验 → 二次确认 → 携带 confirm_token 提交）
 */
async function submitEdit(): Promise<void> {
  const target = editTarget.value
  if (!target) return
  let conditions: Record<string, any>
  try {
    conditions = JSON.parse(editForm.conditions || '{}')
    if (!conditions || typeof conditions !== 'object' || Array.isArray(conditions)) {
      throw new Error('条件必须为 JSON 对象')
    }
    jsonError.value = ''
  } catch (e: any) {
    jsonError.value = `条件 JSON 解析失败：${e?.message || '语法错误'}`
    ElMessage.warning('条件 JSON 语法有误，请修正后再提交')
    return
  }
  if (!editForm.reason.trim()) {
    ElMessage.warning('请填写变更原因（必填）')
    return
  }
  try {
    await ElMessageBox.confirm(
      '档位/阈值变更将直接影响线上分级判定，确认提交本次规则变更？',
      '二次确认',
      { type: 'warning', confirmButtonText: '确认提交', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  saving.value = true
  try {
    await adminApi.triageRuleUpdate(target.rule_id, {
      title: editForm.title.trim(),
      level: editForm.level,
      priority: Number(editForm.priority),
      conditions,
      basis: editForm.basis.trim(),
      observations: arrOf(editForm.observations),
      escalation_flags: arrOf(editForm.escalation_flags),
      contraindications: arrOf(editForm.contraindications),
      disclaimers: arrOf(editForm.disclaimers),
      status: editForm.status,
      reason: editForm.reason.trim(),
      confirm_token: CONFIRM_TOKEN,
    })
    ElMessage.success('规则已保存')
    editVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '规则保存失败')
  } finally {
    saving.value = false
  }
}

/**
 * 函数级注释：打开专家会签对话框
 * @param row 规则行数据
 */
function openSignoff(row: TriageRuleItem): void {
  signoffTarget.value = row
  signoffForm.expert_signoff = row.expert_signoff || ''
  signoffForm.note = ''
  signoffVisible.value = true
}

/**
 * 函数级注释：提交专家会签（成功后刷新列表，gate_ready 随之变化）
 */
async function submitSignoff(): Promise<void> {
  const target = signoffTarget.value
  if (!target) return
  const name = signoffForm.expert_signoff.trim()
  if (name.length < 2) {
    ElMessage.warning('请填写签署人（姓名 / 工号，至少 2 个字符）')
    return
  }
  signing.value = true
  try {
    await adminApi.triageRuleReview(target.rule_id, {
      expert_signoff: name,
      note: signoffForm.note.trim() || undefined,
    })
    ElMessage.success('会签已留痕')
    signoffVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '会签提交失败')
  } finally {
    signing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.triage-page {
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

.head-meta {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}

/* 门禁条 */
.gate-detail {
  margin-top: 4px;
  font-size: var(--fs-caption);
  line-height: 1.7;
}

.gate-ok {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
}

.gate-ok-text {
  font-size: var(--fs-sub);
  color: var(--ink-2);
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

/* 筛选行 */
.filter-card {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  padding: 14px 24px;
}

.f-label {
  font-size: var(--fs-sub);
  color: var(--ink-2);
}

.f-ctrl {
  width: 240px;
}

.f-hint {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

/* 场景分组 */
.scene-card {
  padding: var(--sp-6);
}

.scene-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.scene-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.scene-meta .warn {
  color: var(--warn);
}

.v-sep {
  color: var(--line-strong);
}

.rule-id {
  font-size: var(--fs-caption);
  color: var(--ink-1);
}

.rule-title {
  color: var(--ink-1);
}

.age-cell {
  font-size: var(--fs-caption);
  color: var(--ink-2);
}

.signoff-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.signoff-name {
  font-size: var(--fs-caption);
  color: var(--ink-1);
}

.signoff-time {
  font-size: 11px;
  color: var(--ink-3);
}

.muted {
  color: var(--ink-3);
}

/* 对话框 */
.dialog-tip {
  margin-bottom: 12px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.field-hint {
  margin-top: 4px;
  font-size: 11px;
  color: var(--ink-3);
  line-height: 1.6;
}

.json-error {
  margin-top: 6px;
  font-size: var(--fs-caption);
  color: var(--danger);
}

.signoff-title {
  color: var(--ink-1);
}

.json-input :deep(textarea) {
  font-family: var(--font-numeric);
  font-size: var(--fs-caption);
  line-height: 1.6;
}

@media (max-width: 640px) {
  .head-card {
    padding: 16px;
  }
  .f-ctrl {
    width: 100%;
  }
}
</style>
