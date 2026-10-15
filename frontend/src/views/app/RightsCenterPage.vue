<!--
  RightsCenterPage SC-25 个人信息权利中心（Stitch 稿重构）
  服务响应承诺卡（法定 15 个工作日 + 进度刻度带）+
  法定权利通道清单卡（六行通道：查阅/更正/复制导出/撤回同意/删除/账号注销）+
  处理中请求追踪卡（工单号 + 处理中标签 + 时效 + st-meter 进度）+ 被驳回说明卡。
  六请求入口 POST /rights/requests 各类型（query/correct/delete/export/withdraw/complaint）
  与导出下载逻辑全保留；账号注销项提交 complaint 工单并引导前往账号安全页二次核验。
-->
<template>
  <div class="page rt-page">
    <!-- 页头 -->
    <header class="rt-head">
      <button class="back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">个人信息权利中心</h1>
    </header>

    <!-- 服务响应承诺卡 -->
    <div class="st-card sla-card">
      <div class="sla-head">
        <span class="sla-label">● 服务响应承诺</span>
        <span class="st-tag st-tag--green st-tag--plain">法定 15 个工作日</span>
      </div>
      <p class="sla-body">
        依法出具答复并办结权利申请，平台将通过系统通知及预留联系方式同步办理进度。
      </p>
      <!-- 进度刻度带：00 天(受理) — 07 天(裁查) — 15 天(法定办结期限) -->
      <div class="sla-scale">
        <div class="ss-labels caption">
          <span>00 天（受理）</span>
          <span>07 天（裁查）</span>
          <span>15 天（法定办结期限）</span>
        </div>
        <div class="ss-band">
          <span class="ss-fill" aria-hidden="true" />
        </div>
      </div>
    </div>

    <!-- 法定权利通道清单卡 -->
    <div class="st-card list-card">
      <div class="lc-head">
        <span class="st-section-head">法定权利通道清单</span>
        <span class="caption">已支持 6 项法定权利</span>
      </div>

      <div v-for="r in RIGHTS" :key="r.type" class="channel-row" :class="{ danger: r.danger }">
        <div class="cr-ico" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path :d="r.icon" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>
        <div class="cr-body">
          <p class="cr-name">
            {{ r.name }}
            <span class="st-tag" :class="r.danger ? 'st-tag--red' : 'st-tag--green'">{{ r.tag }}</span>
          </p>
          <p class="cr-desc caption">{{ r.desc }}</p>
        </div>
        <button
          class="cr-btn touch-target"
          :class="{ main: r.main, red: r.danger }"
          type="button"
          @click="openRequest(r)"
        >
          {{ r.action }}
        </button>
      </div>
    </div>

    <!-- 处理中请求追踪卡 -->
    <div v-if="tracking" class="st-card track-card">
      <div class="tc-head">
        <span class="st-section-head">处理中请求追踪</span>
        <!-- 完整工单号回显，点击复制 -->
        <span
          class="st-tag st-tag--outline st-tag--plain numeric tc-no"
          title="点击复制完整编号"
          @click="copyTrackingNo"
        >工单 {{ trackingNo }}</span>
      </div>
      <div class="tc-item">
        <div class="tc-line">
          <p class="tc-name">{{ typeLabel(tracking.request_type) }}</p>
          <span class="st-tag st-tag--amber">● 处理中</span>
        </div>
        <p class="caption tc-meta">
          提交时间：{{ fmtTime(tracking.created_at) }}
          <span class="tc-sep">|</span>
          办理时效：预计剩余 {{ remainDays }} 天
        </p>
        <div class="tc-progress">
          <span class="caption">材料审核通过</span>
          <span class="caption">数据归档阶段（{{ trackPct }}%）</span>
        </div>
        <div class="st-meter">
          <span class="st-meter__fill" :style="{ width: trackPct + '%' }" />
        </div>
        <p class="caption tc-send" v-if="tracking.request_type === 'export'">完成后将发至邮箱或可在列表下载</p>
      </div>
    </div>

    <!-- 被驳回时说明卡 -->
    <div class="st-note rt-note">
      <svg class="note-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
      <p><strong>被驳回时：</strong>平台将依法出具具体理由并提供申诉入口。用户可凭回执单号提交二次复议。</p>
    </div>

    <!-- 我的请求列表（原状态跟踪保留） -->
    <div v-if="requests.length" class="st-card list-card">
      <div class="lc-head">
        <span class="st-section-head">我的请求</span>
      </div>
      <div v-for="(q, i) in requests" :key="i" class="req-row">
        <div>
          <p class="req-name">{{ typeLabel(q.request_type) }}</p>
          <p class="caption req-time">{{ fmtTime(q.created_at) }}</p>
          <!-- 完整回执编号（request_no，如 RT2026…） -->
          <p v-if="q.request_no" class="caption req-no numeric">{{ q.request_no }}</p>
        </div>
        <span class="req-status" :class="q.status">{{ statusLabel(q.status) }}</span>
        <button v-if="q.request_type === 'export' && q.status === 'done'" class="cr-btn main" @click.stop="download(q)">
          下载
        </button>
      </div>
    </div>

    <!-- 发起请求弹窗 -->
    <el-dialog v-model="reqVisible" :title="`申请「${currentType?.name}」`" width="88%" :append-to-body="true">
      <p class="req-note caption">{{ currentType?.note }}</p>
      <el-input
        v-model="reqNote"
        type="textarea"
        :rows="3"
        maxlength="300"
        placeholder="补充说明（选填，如涉及的具体档案昵称）"
      />
      <template #footer>
        <div class="dlg-actions">
          <el-button @click="reqVisible = false">取消</el-button>
          <el-button type="primary" :loading="submitting" @click="submit">提交请求</el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 底行 -->
    <p class="gdpr-foot caption">数据保护协议合规编码：GDPR-CN-2026-V3.4</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { createRightsRequest, getRightsRequests } from '@/api/client'

/**
 * 六类权利请求（name/desc 按 SC-25 稿；type 为页面内部标识，
 * apiType 对齐后端 rights_api 枚举 access/correct/export/withdraw/delete/deactivate，
 * 原页面 type 的 query/complaint 不在后端 Literal 枚举内，直接提交会被 422 拒绝）
 */
const RIGHTS = [
  {
    type: 'query',
    apiType: 'access',
    name: '查阅我的信息',
    tag: '实时在线',
    desc: '档案 · 问答 · 报告 · 同步记录',
    action: '查看',
    main: false,
    danger: false,
    icon: 'M4 6.5A2.5 2.5 0 0 1 6.5 4h7L18 8.5V19a1 1 0 0 1-1 1H6.5A2.5 2.5 0 0 1 4 17.5v-11ZM13.5 4v4.5H18M8 13h6M8 16.5h4',
    note: '我们将整理你在本产品内的全部个人信息清单。'
  },
  {
    type: 'correct',
    apiType: 'correct',
    name: '更正信息',
    tag: '部分审核',
    desc: '档案可自助修改；系统日志类仅支持申请更正',
    action: '申请',
    main: false,
    danger: false,
    icon: 'M4 20h4l10-10-4-4L4 16v4ZM14 6l4 4',
    note: '请说明需更正的内容与正确信息。'
  },
  {
    type: 'export',
    apiType: 'export',
    name: '复制与导出',
    tag: '双格式',
    desc: '支持导出 JSON / CSV 格式至邮箱或本地',
    action: '导出',
    main: true,
    danger: false,
    icon: 'M12 4v10m0 0 4-4m-4 4-4-4M5 20h14',
    note: '导出完成后可在下方列表下载。'
  },
  {
    type: 'withdraw',
    apiType: 'withdraw',
    name: '撤回同意',
    tag: '权限解除',
    desc: '分项撤回基础同意或儿童信息单独同意',
    action: '撤回',
    main: false,
    danger: false,
    icon: 'M9 14l-4-4 4-4m-4 4h11a4 4 0 0 1 0 8h-5',
    note: '也可在"账号安全"页直接撤回常用授权。'
  },
  {
    type: 'delete',
    apiType: 'delete',
    name: '删除个人信息',
    tag: '高敏感度',
    desc: '删除后不可恢复，法定留存交易除外',
    action: '删除',
    main: false,
    danger: true,
    icon: 'M5 7h14M9 7V5h6v2m-8 0 1 13h8l1-13M10 11v5m4-5v5',
    note: '删除后不可恢复，法定留存交易除外，请谨慎确认范围。'
  },
  {
    type: 'complaint',
    // 账号注销对应后端 deactivate 枚举（complaint 非法，会被 422 拒绝）
    apiType: 'deactivate',
    name: '账号注销',
    tag: '永久解除',
    desc: '注销流程与二次身份核验',
    action: '注销',
    main: false,
    danger: false,
    icon: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm-3 9h6',
    note: '提交注销申请工单后，请前往「账号与安全」页完成二次身份核验。'
  }
]

/** 请求列表 */
const requests = ref<any[]>([])
const loading = ref(true)
/** 弹窗 */
const reqVisible = ref(false)
const currentType = ref<(typeof RIGHTS)[number] | null>(null)
const reqNote = ref('')
const submitting = ref(false)

/** 静态进度演示：数据归档阶段百分比（不照抄演示数字，按已过天数推导） */
const trackPct = computed<number>(() => {
  const d = remainDays.value
  return Math.max(20, Math.min(90, 80 - (7 - d) * 5))
})

/** 第一个处理中请求（追踪卡数据源）：后端提交后初始 status=submitted（rights_api），processing 为处理中间态 */
const tracking = computed<any>(
  () => requests.value.find((q) => q.status === 'submitted' || q.status === 'processing') || null
)

/** 追踪工单号（后端 request_no 完整回显，如 RT2026…；缺省回退 id，不再截断改写） */
const trackingNo = computed<string>(() => String(tracking.value?.request_no || tracking.value?.id || ''))

/**
 * 办理剩余天数（15 工作日按自然日近似）
 * @returns 0~15 整数
 */
const remainDays = computed<number>(() => {
  const t = tracking.value?.created_at
  if (!t) return 15
  const passed = Math.floor((Date.now() - new Date(t).getTime()) / 86400000)
  return Math.max(0, Math.min(15, 15 - passed))
})

/**
 * 加载请求列表
 * @throws 失败静默保留空态
 */
async function load(): Promise<void> {
  loading.value = true
  try {
    const res: any = await getRightsRequests()
    // 后端契约：GET /rights/requests 返回 {requests: [...]}（旧字段 items 兼容保留）
    requests.value = res?.requests || res?.items || []
  } catch {
    requests.value = []
  } finally {
    loading.value = false
  }
}

/**
 * 打开发起弹窗
 * @param r 请求类型
 */
function openRequest(r: (typeof RIGHTS)[number]): void {
  currentType.value = r
  reqNote.value = ''
  reqVisible.value = true
}

/**
 * 提交请求
 * @throws 失败消息提示
 */
async function submit(): Promise<void> {
  if (!currentType.value) return
  submitting.value = true
  try {
    await createRightsRequest({
      // 提交后端合法枚举（apiType），页面内部标识 type 不直接上传
      request_type: (currentType.value as any).apiType || currentType.value.type,
      // 后端 RightsRequestBody 契约为 {request_type, scope}：补充说明放入 scope.note，
      // 避免 note 字段被服务端忽略导致诉求丢失
      scope: reqNote.value.trim() ? { note: reqNote.value.trim() } : undefined
    })
    ElMessage.success(
      currentType.value.type === 'complaint'
        ? '注销申请工单已提交，请前往「账号与安全」页完成二次身份核验'
        : '请求已提交，处理进展将在下方更新'
    )
    reqVisible.value = false
    load()
  } catch (e: any) {
    ElMessage.error(e?.message || '提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

/**
 * 类型中文标签（同时匹配页面内部 type 与后端 apiType 枚举：
 * 「我的请求」列表回显的 request_type 为后端枚举值 access/deactivate 等）
 * @param t 类型码
 * @returns 标签
 */
function typeLabel(t: string): string {
  return RIGHTS.find((r) => r.type === t || (r as any).apiType === t)?.name || t
}

/**
 * 状态中文标签（对齐后端 rights_api 枚举：submitted/processing 为处理中）
 * @param s 状态码
 * @returns 标签
 */
function statusLabel(s: string): string {
  return (
    {
      submitted: '处理中',
      processing: '处理中',
      pending: '处理中',
      done: '已完成',
      rejected: '已驳回'
    }[s] || s || '处理中'
  )
}

/**
 * 时间格式化
 * @param ts ISO 时间
 * @returns 本地时间串
 */
function fmtTime(ts: string): string {
  return ts ? new Date(ts).toLocaleString('zh-CN') : ''
}

/**
 * 下载导出文件（演示：以 JSON Blob 下载）
 * @param q 请求记录
 */
function download(q: any): void {
  const blob = new Blob([JSON.stringify(q.export_data || q, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `jiaban-export-${q.id || Date.now()}.json`
  a.click()
  URL.revokeObjectURL(url)
}

/**
 * 复制追踪工单完整编号到剪贴板
 * @throws 剪贴板不可用时提示失败
 */
async function copyTrackingNo(): Promise<void> {
  if (!trackingNo.value) return
  try {
    await navigator.clipboard.writeText(trackingNo.value)
    ElMessage.success('工单编号已复制')
  } catch {
    ElMessage.error('复制失败，请手动记录编号')
  }
}

onMounted(load)
</script>

<style lang="scss" scoped>
/* ---------- 页头 ---------- */
.rt-head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);

  .back {
    width: 32px;
    height: 32px;
    border: none;
    background: none;
    color: var(--ink-2);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;

    svg { width: 20px; height: 20px; }
  }

  .head-title {
    flex: 1;
    text-align: center;
    font-size: var(--fs-title);
    font-weight: 600;
    color: var(--ink-1);
  }
}

/* ---------- 服务响应承诺卡 ---------- */
.sla-card {
  margin-bottom: var(--sp-4);
}

.sla-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-2);

  .sla-label {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
  }
}

.sla-body {
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.7;
  margin-bottom: var(--sp-4);
}

.sla-scale {
  .ss-labels {
    display: flex;
    justify-content: space-between;
    color: var(--ink-3);
    margin-bottom: var(--sp-2);

    span:nth-child(2) {
      transform: translateX(10px);
    }
  }

  .ss-band {
    position: relative;
    height: 6px;
    border-radius: var(--radius-pill);
    background: var(--surface-2);
    overflow: hidden;

    .ss-fill {
      position: absolute;
      left: 0;
      top: 0;
      height: 100%;
      width: 46%;
      border-radius: var(--radius-pill);
      background: var(--accent);
    }
  }
}

/* ---------- 通道清单卡 ---------- */
.list-card {
  margin-bottom: var(--sp-4);
  padding: var(--sp-4) var(--sp-6);
}

.lc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-3);

  > .caption {
    color: var(--ink-3);
  }
}

.channel-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;

  & + .channel-row {
    border-top: 1px dashed var(--line);
  }

  &.danger {
    .cr-ico {
      background: var(--danger-soft);
      color: var(--danger);
    }
  }
}

.cr-ico {
  flex: none;
  width: 36px;
  height: 36px;
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  color: var(--ink-2);
  display: flex;
  align-items: center;
  justify-content: center;

  svg { width: 18px; height: 18px; }
}

.cr-body {
  flex: 1;

  .cr-name {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
  }

  .cr-desc {
    margin-top: 2px;
    line-height: 1.6;
  }
}

.cr-btn {
  flex: none;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  padding: 6px 16px;
  border-radius: var(--radius-ctl);
  cursor: pointer;

  &.main {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);
    font-weight: 600;
  }

  &.red {
    border-color: var(--danger);
    color: var(--danger);
  }

  &:active {
    opacity: 0.85;
  }
}

/* ---------- 追踪卡 ---------- */
.track-card {
  margin-bottom: var(--sp-4);
}

.tc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-3);

  /* 完整工单号可点击复制 */
  .tc-no {
    cursor: pointer;

    &:active {
      opacity: 0.8;
    }
  }
}

.tc-item {
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);

  .tc-line {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .tc-name {
      font-size: var(--fs-sub);
      font-weight: 600;
      color: var(--ink-1);
    }
  }

  .tc-meta {
    margin: var(--sp-2) 0;
    color: var(--ink-3);

    .tc-sep {
      margin: 0 var(--sp-2);
      color: var(--line-strong);
    }
  }

  .tc-progress {
    display: flex;
    justify-content: space-between;
    margin-bottom: var(--sp-2);

    span:last-child {
      color: var(--accent);
      font-weight: 600;
    }
  }

  .st-meter {
    margin-bottom: var(--sp-2);
  }

  .tc-send {
    color: var(--ink-3);
  }
}

/* ---------- 免责/说明条 ---------- */
.rt-note {
  margin-bottom: var(--sp-4);
}

/* ---------- 我的请求列表 ---------- */
.req-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-top: 1px dashed var(--line);

  > div:first-child {
    flex: 1;
  }
}

.req-name {
  font-size: var(--fs-sub);
  color: var(--ink-1);
}

.req-time {
  margin-top: 2px;
}

/* 完整回执编号行 */
.req-no {
  margin-top: 2px;
  color: var(--ink-3);
  word-break: break-all;
}

.req-status {
  font-size: var(--fs-caption);
  color: var(--warn);
  flex-shrink: 0;

  &.done {
    color: var(--accent);
  }

  &.rejected {
    color: var(--danger);
  }
}

.req-note {
  margin-bottom: var(--sp-3);
}

.dlg-actions {
  display: flex;
  gap: var(--sp-3);

  .el-button {
    flex: 1;
  }
}

.gdpr-foot {
  text-align: center;
  padding-bottom: var(--sp-4);
}
</style>
