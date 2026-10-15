<!--
  RiskBlockPage SC-12 风险拦截全屏（Stitch 稿重构）
  拦截卡（已停止生成回答 + 不展示原文/无建议文本 + 拦截级别刻度 + 拦截原因行；
  红仅落在停止图标与当前档读数/游标，卡面保持中性）+ 安全规约检测行 +
  危机干预求助渠道列表（六渠道基准：110/12355 有值，其余显示「暂未开通」徽章、不渲染按钮）
  + 复制求助信息兜底 + 我知道了（次级描边）+ 软类别（appeal_allowed）
  「这不是高风险，我要继续提问」（跳申诉）；硬类别隐藏。
  入参（query）：session=会话uid, data=blocked 事件 JSON（编码）。
-->
<template>
  <div class="risk-page">
    <div class="risk-body">
      <!-- 拦截卡：单卡单锚点（红只落在图标与级别读数上） -->
      <div class="stop-card">
        <div class="stop-icon">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.9" />
            <path d="M7.5 12h9" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" />
          </svg>
        </div>
        <h1 class="stop-title">已停止生成回答</h1>
        <p class="stop-desc">为保护你与孩子，本页不展示你的原文，也不提供任何诊断或建议文本。</p>
        <GraduatedBand
          class="stop-band"
          label="拦截级别"
          tone="danger"
          :bands="BAND_NAMES"
          :value="severityValue"
          :partial="!hasBlockedData"
        />
        <p class="stop-reason">
          <i class="dot" aria-hidden="true" />
          拦截原因：{{ riskCategory }} · 本次不计提问次数
        </p>
      </div>

      <!-- 安全规约检测行：系统行为说明（级别读数由上方刻度承担） -->
      <div class="check-line">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
        </svg>
        <span>安全规约检测已拦截</span>
        <i class="cl-sep" aria-hidden="true" />
        <span>毫秒级阻断响应</span>
      </div>

      <!-- 危机干预求助渠道 -->
      <div class="ch-sec-head">
        <h2 class="st-section-head">危机干预求助渠道</h2>
        <span class="ch-sec-tip">请即刻联系专业机构</span>
      </div>

      <div class="channel-list">
        <div v-for="c in channelRows" :key="c.code" class="ch-row">
          <div class="ch-info">
            <p class="ch-name">
              {{ c.name }}
              <span v-if="c.number" class="ch-num numeric">{{ c.number }}</span>
              <span v-if="c.number" class="badge red">{{ c.badgeActive }}</span>
              <span v-else class="badge gray">{{ c.badgeIdle }}</span>
            </p>
            <p class="ch-desc" :class="{ danger: c.descDanger }">{{ c.desc }}</p>
            <!-- 沟通参考引用块 -->
            <p v-if="c.script" class="ch-script">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M4 6h16v10H8l-4 4V6Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
              </svg>
              沟通参考： "{{ c.script }}"
            </p>
          </div>
          <div v-if="c.number || c.mapQuery" class="ch-actions">
            <template v-if="c.number">
              <a class="act call touch-target" :href="`tel:${c.number}`" :aria-label="`拨打 ${c.name} ${c.number}`">拨打</a>
              <button class="act copy touch-target" type="button" @click="copyNumber(c.number)">{{ copiedCode === c.code ? '已复制' : '复制' }}</button>
            </template>
            <a
              v-else-if="c.mapQuery"
              class="act find touch-target"
              :href="mapUrl(c.mapQuery)"
              target="_blank"
              rel="noopener noreferrer"
            >{{ c.actionLabel }}</a>
            <!-- 无动作渠道不渲染按钮形状：未开通状态由行内徽章说明 -->
          </div>
        </div>
        <p v-if="!channelRows.length" class="no-channel caption">求助渠道信息加载中或暂未配置</p>
      </div>

      <!-- 兜底动作：渠道信息可整段复制带走（号码不全时仍可用） -->
      <button class="copy-help touch-target" type="button" @click="copyHelpInfo">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="9" y="9" width="11" height="11" rx="2" stroke="currentColor" stroke-width="1.75" />
          <path d="M15 5.5A1.5 1.5 0 0 0 13.5 4h-8A1.5 1.5 0 0 0 4 5.5v8A1.5 1.5 0 0 0 5.5 15" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
        </svg>
        复制求助信息
      </button>
    </div>

    <!-- 操作区：主行动在渠道行内（拨打），此处均为次级出口 -->
    <div class="risk-actions">
      <el-button size="large" plain class="ack-btn" data-exit @click="ack">我知道了</el-button>
      <!-- 申诉跳转带上 blocked 帧的 risk_event_no：申诉页拦截记录编号可回显（无编号时申诉页仍显示占位文案） -->
      <!-- SIM-19 口径留证：申诉入口仅软类别（appeal_allowed=true）展示。
           PRD《家伴-PRD_V1.5.md》§7.9.2 第 4 条：硬类别「永不自动放行，复核只能『维持拦截』
           或『转人工线下引导』」；§7.9.4：「硬类别 → 不提供『继续提问』出口，只显示渠道清单」；
           §8.2 高危清单表：硬类别处置为「拦截 + 危机渠道；不提供『继续提问』出口」，仅软类别
           「复核通过可放行」。故硬类别拦截页隐藏申诉按钮（blocked 帧 appeal_allowed=false）。 -->
      <el-button
        v-if="appealAllowed"
        link
        class="appeal-btn touch-target"
        @click="$router.push({ path: '/app/appeal', query: { session: sessionId, risk_no: riskEventNo } })"
      >
        这不是高风险，我要继续提问
      </el-button>
      <AiDisclaimer ai-label="AI 生成内容" disclaimer="仅供参考，不替代医生诊断" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AiDisclaimer from '@/components/AiDisclaimer.vue'
import GraduatedBand from '@/components/GraduatedBand.vue'

const route = useRoute()
const router = useRouter()

/** 关联会话 uid */
const sessionId = computed(() => (route.query.session as string) || '')

/** blocked 事件数据 */
const blockedData = ref<any>({})

/** blocked 数据是否有效（直接打开页面无数据 → 刻度呈信息不足态） */
const hasBlockedData = computed(() => Object.keys(blockedData.value || {}).length > 0)

/** 是否允许申诉（软类别 true） */
const appealAllowed = ref(false)

/** 拦截级别档位（低→高） */
const BAND_NAMES = ['关注', '高风险', '危机']

/** 拦截级别落点：软类别（可申诉）→ 高风险；硬类别 → 危机 */
const severityValue = computed(() => {
  if (!hasBlockedData.value) return 0.5
  return appealAllowed.value ? 1 / 2 : 5 / 6
})

/** 拦截原因类别显示名 */
const riskCategory = ref('命中高危类别')
/** 复制中的渠道 code（2s 复位） */
const copiedCode = ref('')

/** 渠道展示元数据（按 channel_code 映射稿面徽章与说明；idle 徽章统一「暂未开通」口径） */
const CHANNEL_META: Record<string, { badgeActive: string; badgeIdle: string; desc: string; descDanger?: boolean; mapQuery?: string; actionLabel?: string }> = {
  police: { badgeActive: '紧急求助', badgeIdle: '暂未开通', desc: '紧急危险情况请立即报警求助' },
  minor: { badgeActive: '保护渠道', badgeIdle: '暂未开通', desc: '号码显示：以官方公布为准', actionLabel: '暂未开通' },
  teen: { badgeActive: '共青团热线', badgeIdle: '暂未开通', desc: '全国青少年心理咨询与法律援助' },
  psych: { badgeActive: '热线', badgeIdle: '接入中', desc: '全国多地精神卫生热线统一接入中', actionLabel: '接入中' },
  pet_emergency: { badgeActive: '急症通道', badgeIdle: '暂未开通', desc: '大出血 / 中毒请立即前往', mapQuery: '宠物医院', actionLabel: '查找就近' },
  animal_bite: { badgeActive: '犬伤处置', badgeIdle: '暂未开通', desc: '儿童被咬抓伤立即前往，不可延误', descDanger: true, mapQuery: '犬伤门诊', actionLabel: '查找门诊' }
}

/** 内置渠道基准（后端未下发时兜底；110/12355 有值，其余 null） */
const FALLBACK_CHANNELS = [
  { channel_code: 'police', channel_name: '紧急报警', phone_number: '110', hours: '全天 24 小时' },
  { channel_code: 'minor', channel_name: '未成年人保护渠道', phone_number: null, hours: '' },
  { channel_code: 'teen', channel_name: '青少年服务台', phone_number: '12355', hours: '工作日 9:00-18:00' },
  { channel_code: 'psych', channel_name: '心理援助热线', phone_number: null, hours: '' },
  { channel_code: 'pet_emergency', channel_name: '宠物急症：本地宠物医院', phone_number: null, hours: '' },
  { channel_code: 'animal_bite', channel_name: '犬伤处置：犬伤门诊 / 疾控', phone_number: null, hours: '' }
]

/**
 * 风险事件编号（blocked 帧多字段名兜底：risk_event_no / risk_no / event_no）
 * 模板申诉跳转透传用；注意必须基于 blockedData（此前误引用未定义的 blocked 恒为空）
 */
const riskEventNo = computed<string>(
  () => blockedData.value?.risk_event_no || blockedData.value?.risk_no || blockedData.value?.event_no || ''
)

/** 渠道行视图模型（号码/说明/沟通参考合并） */
const channelRows = computed(() => {
  return (blockedData.value?.channels || FALLBACK_CHANNELS).map((c: any) => {
    const meta = CHANNEL_META[c.channel_code] || { badgeActive: '服务渠道', badgeIdle: '待接入', desc: c.hours || '请联系线下专业机构' }
    return {
      code: c.channel_code || c.channel_name,
      name: c.channel_name,
      number: c.phone_number || '',
      script: c.script || '',
      ...meta
    }
  })
})

/**
 * 生成地图检索外链（查找就近医院/门诊）
 * @param query 检索词
 * @returns 地图检索 URL
 */
function mapUrl(query: string): string {
  return `https://ditu.amap.com/search?query=${encodeURIComponent(query)}`
}

/**
 * 复制号码到剪贴板
 * @param number 号码
 */
async function copyNumber(number: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(number)
    copiedCode.value = number
    ElMessage.success('号码已复制')
    setTimeout(() => (copiedCode.value = ''), 2000)
  } catch {
    ElMessage.error('复制失败，请手动记录号码')
  }
}

/**
 * 复制整段求助信息（名称 + 号码/去向），供粘贴到其他应用或发送给家人
 */
async function copyHelpInfo(): Promise<void> {
  const lines = channelRows.value.map((c: any) => {
    const num = c.number ? ` ${c.number}` : ''
    const hint = !c.number && c.actionLabel ? `（${c.actionLabel}）` : ''
    return `· ${c.name}${num}${hint}`
  })
  const text = ['小光景求助信息（请尽快联系专业机构）', ...lines].join('\n')
  try {
    await navigator.clipboard.writeText(text)
    ElMessage.success('求助信息已复制，可粘贴发送给家人')
  } catch {
    ElMessage.error('复制失败，请手动记录号码')
  }
}

/**
 * 挂载时解析 query 中的 blocked 数据
 */
onMounted(() => {
  try {
    const raw = route.query.data as string
    if (raw) blockedData.value = JSON.parse(decodeURIComponent(raw))
  } catch {
    blockedData.value = {}
  }
  const d = blockedData.value
  appealAllowed.value = !!d?.appeal_allowed
  // 拦截原因行展示类别短标签（reason 为长句不在此展示）
  if (d?.risk_category_label) riskCategory.value = d.risk_category_label
})

/**
 * 确认知晓：返回首页并携带 replace 避免回退回到流页
 */
function ack(): void {
  router.replace('/app/home')
}
</script>

<style lang="scss" scoped>
.risk-page {
  min-height: 100vh;
  background: var(--bg);
  display: flex;
  flex-direction: column;
}

.risk-body {
  flex: 1;
  padding: var(--sp-6) var(--sp-6) var(--sp-4);
}

/* ===== 拦截卡：中性面 + 单红锚点 ===== */
.stop-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-8) var(--sp-6);
  text-align: left;
}

/* 唯一红锚点：图标 */
.stop-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--danger-soft);
  color: var(--danger);
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: var(--sp-3);

  svg { width: 24px; height: 24px; }
}

.stop-title {
  font-size: var(--fs-display);
  font-weight: 700;
  color: var(--ink-1);
}

.stop-desc {
  margin-top: var(--sp-2);
  font-size: var(--fs-body);
  color: var(--ink-2);
  line-height: 1.7;
}

/* 拦截级别刻度：红只落在当前档读数与游标（见 GraduatedBand tone=danger） */
.stop-band {
  margin-top: var(--sp-3);
}

.stop-reason {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--ink-2);

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--ink-3);
    flex: none;
  }
}

/* ===== 安全规约检测行 ===== */
.check-line {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-top: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  border: 1px solid var(--line);
  font-size: var(--fs-caption);
  color: var(--ink-2);

  svg { width: 15px; height: 15px; color: var(--accent); flex: none; }

  .cl-sep {
    width: 1px;
    height: 12px;
    background: var(--line-strong);
  }
}

/* ===== 渠道区 ===== */
.ch-sec-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-top: var(--sp-6);
  margin-bottom: var(--sp-3);

  .ch-sec-tip {
    font-size: var(--fs-caption);
    color: var(--ink-3);
  }
}

.channel-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.ch-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-4);
}

.ch-info {
  flex: 1;
  min-width: 0;
}

.ch-name {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: var(--fs-sub);
  font-weight: 700;
  color: var(--ink-1);

  .ch-num {
    color: var(--ink-1);
    font-size: var(--fs-body);
  }
}

/* 渠道徽章 */
.badge {
  font-size: 11px;
  font-weight: 500;
  padding: 1px 7px;
  border-radius: 4px;
  white-space: nowrap;

  &.red {
    background: var(--danger-soft);
    color: var(--danger);
    border: 1px solid color-mix(in srgb, var(--danger) 30%, transparent);
  }

  &.gray {
    background: var(--surface-2);
    color: var(--ink-3);
    border: 1px solid var(--line);
  }
}

.ch-desc {
  margin-top: 3px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
  line-height: 1.6;

  /* 危险强调描述（犬伤处置） */
  &.danger { color: var(--danger); }
}

/* 沟通参考引用块 */
.ch-script {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  border: 1px solid var(--line);
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.6;

  svg { width: 14px; height: 14px; flex: none; margin-top: 2px; color: var(--ink-3); }
}

/* 渠道动作按钮 */
.ch-actions {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  flex: none;
}

.act {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  padding: 6px 14px;
  border-radius: var(--radius-ctl);
  font-size: var(--fs-caption);
  text-decoration: none;
  cursor: pointer;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink-1);
  text-align: center;

  &.call {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);
    font-weight: 600;
  }

  &.find {
    background: var(--surface-2);
    border-color: var(--line);
    color: var(--ink-2);
  }
}

/* 兜底：复制求助信息（次级描边整行按钮） */
.copy-help {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  width: 100%;
  min-height: var(--touch-min);
  margin-top: var(--sp-3);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--ink-1);
  font-size: var(--fs-sub);
  cursor: pointer;

  svg { width: 16px; height: 16px; color: var(--ink-2); flex: none; }
}

.no-channel {
  color: var(--ink-3);
}

/* ===== 操作区 ===== */
.risk-actions {
  padding: var(--sp-4) var(--sp-6) calc(var(--sp-4) + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);

  .el-button {
    width: 100%;
    margin: 0;
  }
}

/* 我知道了：次级描边（主行动在渠道行内） */
.ack-btn {
  background: var(--surface);
  border-color: var(--line-strong);
  color: var(--ink-1);
  font-weight: 500;
}

/* 申诉出口：文字级次要操作 */
.appeal-btn {
  color: var(--ink-2);
  font-size: var(--fs-caption);
}
</style>
