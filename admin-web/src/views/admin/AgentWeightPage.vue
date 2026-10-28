<!--
  文件级注释：Agent 展示权重配置页（PRD F12.7 / AC-F12-07-1~3）。
  功能：读取当前 child/pet 权重、超管二次确认后保存新版本、查看历史并一键回滚。
  约束：安全分节（safety）pinned=true 固定置顶，不参与权重排序，页面只允许配置 child/pet。
-->
<template>
  <div class="weight-page">
    <!-- 页头 -->
    <header class="page-head">
      <div>
        <h2>Agent 展示权重</h2>
        <p class="page-sub">F12.7 · 影响家庭综合入口非安全分节的展示顺序；安全分节固定置顶、不参与权重排序。</p>
      </div>
      <el-tag type="info" effect="plain" class="ver-tag">当前版本 v{{ current.version }}</el-tag>
    </header>

    <!-- 权重配置卡 -->
    <section class="card" v-loading="loading">
      <div class="card-head">
        <h3>当前生效权重</h3>
        <span class="muted">修改后 60 秒内全量生效；每次变更均写版本与审计留痕。</span>
      </div>

      <div class="weight-row">
        <div class="weight-item">
          <label>育儿 Agent（child）</label>
          <el-slider v-model="childWeight" :min="0" :max="1" :step="0.05" show-input />
        </div>
        <div class="weight-item">
          <label>宠物 Agent（pet）</label>
          <div class="pet-value numeric">{{ petWeight.toFixed(2) }}</div>
          <p class="hint">自动等于 1 − child 权重，保证归一化。</p>
        </div>
        <div class="weight-item">
          <label>安全分节（safety）</label>
          <div class="pinned-value">置顶固定 · 不参与排序</div>
        </div>
      </div>

      <el-input
        v-model="reason"
        type="textarea"
        :rows="2"
        maxlength="128"
        show-word-limit
        placeholder="请填写变更原因（必填，≥4 字），将写入版本历史与审计记录"
      />
      <div class="actions">
        <el-button @click="load">重置</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存并发布</el-button>
      </div>
    </section>

    <!-- 历史版本卡 -->
    <section class="card" v-loading="loading">
      <div class="card-head">
        <h3>版本历史</h3>
        <span class="muted">回滚以新版本形式生效，不回写旧版本。</span>
      </div>
      <el-table :data="history" size="small" empty-text="暂无变更历史">
        <el-table-column prop="version" label="版本" width="80">
          <template #default="{ row }">
            <span class="numeric">v{{ row.version }}</span>
            <el-tag v-if="row.status === 'active'" size="small" type="success" class="ml6">生效中</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="权重" min-width="180">
          <template #default="{ row }">
            <span class="numeric">child {{ row.weights.child }} / pet {{ row.weights.pet }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="reason" label="变更原因" min-width="220" show-overflow-tooltip />
        <el-table-column prop="effective_at" label="生效时间" width="190">
          <template #default="{ row }"><span class="numeric">{{ row.effective_at || '--' }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="90" align="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" :disabled="row.status === 'active'" @click="openRollback(row)">
              回滚
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 回滚确认 -->
    <el-dialog v-model="rollbackVisible" title="回滚 Agent 权重" width="420px">
      <p class="dialog-text">目标版本：<b class="numeric">v{{ rollbackVersion }}</b></p>
      <el-input
        v-model="rollbackReason"
        type="textarea"
        :rows="2"
        maxlength="128"
        placeholder="请填写回滚原因（必填，≥4 字）"
      />
      <template #footer>
        <el-button @click="rollbackVisible = false">取消</el-button>
        <el-button type="danger" :loading="rolling" @click="confirmRollback">确认回滚</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：Agent 展示权重页逻辑。
 * 数据来源：GET /admin/agent-weights / GET /admin/agent-weights/history；
 * 写操作：PUT /admin/agent-weights、POST /admin/agent-weights/rollback（均需 CONFIRMED 二次确认）。
 */
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { adminApi, ApiError } from '@/api/admin'

/** 当前生效权重视图 */
const current = ref<any>({ weights: { child: 0.5, pet: 0.5 }, version: 0 })
/** 历史版本 */
const history = ref<any[]>([])
/** 育儿权重滑块值（宠物自动取 1 − child） */
const childWeight = ref(0.5)
/** 变更原因 */
const reason = ref('')
/** 加载/保存/回滚中标记 */
const loading = ref(false)
const saving = ref(false)
const rolling = ref(false)
/** 回滚弹窗状态 */
const rollbackVisible = ref(false)
const rollbackVersion = ref(0)
const rollbackReason = ref('')

/** 宠物权重（归一化约束：与育儿权重互补） */
const petWeight = computed(() => {
  const child = Number(childWeight.value) || 0
  return Math.max(0, Math.min(1, 1 - child))
})

/**
 * 函数级注释：加载当前权重与版本历史
 * @returns Promise<void>
 * @throws ApiError 无权限或接口异常时由调用处给出提示
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const data: any = await adminApi.agentWeights()
    current.value = data
    childWeight.value = Number(data?.weights?.child ?? 0.5)
    reason.value = ''
    const hist: any = await adminApi.agentWeightHistory(20)
    history.value = Array.isArray(hist?.items) ? hist.items : []
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '权重配置加载失败')
  } finally {
    loading.value = false
  }
}

/**
 * 函数级注释：保存新权重版本（二次确认 + 变更原因必填）
 * @returns Promise<void>
 */
async function save(): Promise<void> {
  const child = Math.round(Number(childWeight.value) * 100) / 100
  if (!reason.value.trim() || reason.value.trim().length < 4) {
    ElMessage.warning('请填写至少 4 个字的变更原因')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认将权重调整为 child ${child.toFixed(2)} / pet ${(1 - child).toFixed(2)}？保存后立即生效。`,
      '二次确认',
      { type: 'warning', confirmButtonText: '确认发布', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  saving.value = true
  try {
    await adminApi.updateAgentWeights({
      weights: { child, pet: Math.round((1 - child) * 100) / 100 },
      reason: reason.value.trim(),
      confirm_token: 'CONFIRMED'
    })
    ElMessage.success('权重已发布')
    await load()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '权重保存失败')
  } finally {
    saving.value = false
  }
}

/**
 * 函数级注释：打开回滚弹窗
 * @param row 历史版本行
 * @returns void
 */
function openRollback(row: any): void {
  rollbackVersion.value = Number(row?.version || 0)
  rollbackReason.value = ''
  rollbackVisible.value = true
}

/**
 * 函数级注释：确认回滚到目标版本（以新版本形式生效）
 * @returns Promise<void>
 */
async function confirmRollback(): Promise<void> {
  if (!rollbackReason.value.trim() || rollbackReason.value.trim().length < 4) {
    ElMessage.warning('请填写至少 4 个字的回滚原因')
    return
  }
  rolling.value = true
  try {
    await adminApi.rollbackAgentWeight({
      version: rollbackVersion.value,
      reason: rollbackReason.value.trim(),
      confirm_token: 'CONFIRMED'
    })
    ElMessage.success(`已回滚并生成 v${rollbackVersion.value} 的新版本`)
    rollbackVisible.value = false
    await load()
  } catch (e) {
    ElMessage.error(e instanceof ApiError ? e.message : '回滚失败')
  } finally {
    rolling.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.weight-page { display: flex; flex-direction: column; gap: 18px; }
.page-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; flex-wrap: wrap; }
.page-head h2 { margin: 0; font-size: 20px; }
.page-sub { margin: 6px 0 0; color: var(--el-text-color-secondary); font-size: 13px; line-height: 1.6; }
.card { background: #fff; border: 1px solid var(--el-border-color-lighter); border-radius: 12px; padding: 18px; }
.card-head { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.card-head h3 { margin: 0; font-size: 15px; }
.muted { color: var(--el-text-color-secondary); font-size: 12px; }
.weight-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 18px; margin-bottom: 16px; }
.weight-item label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 8px; }
.pet-value { font-size: 22px; font-weight: 700; }
.pinned-value { color: var(--el-color-info); font-size: 14px; }
.hint { margin: 4px 0 0; color: var(--el-text-color-secondary); font-size: 12px; }
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 14px; }
.numeric { font-variant-numeric: tabular-nums; font-family: 'SFMono-Regular', Consolas, monospace; }
.ml6 { margin-left: 6px; }
.dialog-text { margin: 0 0 12px; }
</style>
