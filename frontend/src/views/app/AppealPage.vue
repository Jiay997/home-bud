<!--
  AppealPage SC-13 申诉页（Stitch 稿重构）
  页头（‹ 风险提示 + 标定校准协议·守护模式行）+ 安全拦截卡（拦截记录编号
  RISK-xxx + 命中参考类别 chip + 不展示原文承诺）+「这可能是一次误报」
  展开卡（补充说明 textarea 0/500 + 附件按钮 + 截图遮盖黄条）+
  申诉状态卡（已受理 + APL 编号 + 24h 时限）+ 危机渠道精简区 +
  提交申诉主按钮 / 返回会话次按钮。
  逻辑保留：appeal_note 提交（createAppeal）、受理编号展示、500 字上限。
-->
<template>
  <div class="page appeal-page">
    <header class="qa-head">
      <button class="head-btn touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">风险提示</h1>
      <span class="head-spacer" aria-hidden="true" />
    </header>

    <!-- 标定校准协议 · 守护模式行 -->
    <div class="protocol-row">
      <span class="pr-label">
        <i class="pr-dot" aria-hidden="true" />
        标定校准协议 · 守护模式
      </span>
      <span class="pr-chip">阶段：一级拦截</span>
    </div>

    <!-- 本次提问已被安全拦截卡 -->
    <section class="block-card">
      <div class="bc-head">
        <span class="bc-ico">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
          </svg>
        </span>
        <strong class="bc-title">本次提问已被安全拦截</strong>
      </div>
      <p class="bc-desc">为保护孩子与家人，本次不生成回答。情况紧急请立即联系线下专业机构。</p>

      <div class="bc-meta">
        <span class="bm-label">拦截记录编号</span>
        <span class="bm-value numeric">{{ riskNoText }}</span>
      </div>
      <div class="bc-meta">
        <span class="bm-label">命中参考类别</span>
        <span class="bm-chip">
          <i class="dot" aria-hidden="true" />
          {{ riskCategory }}
        </span>
      </div>

      <p class="bc-promise">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Zm0 5v5m0 2.5v.5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        不展示你的原始提问文本，也不回显命中的具体词条。
      </p>
    </section>

    <!-- 这可能是一次误报展开卡（内含补充说明表单） -->
    <details class="mistake-card" :open="submitted">
      <summary>
        <svg class="swap" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M7 8h10m0 0-3-3m3 3-3 3M17 16H7m0 0 3-3m-3 3 3 3" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        这可能是一次误报
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="m7 10 5 5 5-5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </summary>

      <!-- 补充说明（选填） -->
      <div class="note-sec">
        <div class="ns-head">
          <strong>补充说明（选填）</strong>
          <span class="ns-count numeric">{{ note.length }}/500</span>
        </div>
        <textarea
          v-model="note"
          class="ns-textarea"
          rows="5"
          maxlength="500"
          placeholder="请在此描述你的实际询问意图或场景背景，以便审核员更准确评估…"
        />
        <button class="attach-btn touch-target" type="button" @click="onAttach">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <rect x="3.5" y="5" width="17" height="14" rx="2" stroke="currentColor" stroke-width="1.75" />
            <path d="m6 15 3.5-3.5 3 3L16 11l2.5 2.5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          附件：截图（选项）
        </button>
        <p class="attach-tip">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
          </svg>
          截图请先遮盖孩子可识别信息（面部特征、姓名、证件及就诊卡号）。
        </p>
      </div>
    </details>

    <!-- 申诉状态卡（提交后显示） -->
    <section v-if="result" class="status-card">
      <header class="sc-head">
        <strong class="sc-title">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M12 3v3m0 12v3M3 12h3m12 0h3M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
          申诉状态
        </strong>
        <span class="sc-badge">已受理</span>
      </header>
      <div class="sc-meta">
        <span class="bm-label">受理编号</span>
        <span class="bm-value numeric">{{ result.appeal_no }}</span>
      </div>
      <div class="sc-meta">
        <span class="bm-label">预计复核时限</span>
        <span class="bm-value">24 小时内</span>
      </div>
      <p class="sc-note">
        已受理：保留本页，不跳转、不会话；复核通过后可主动重新提交。
      </p>
    </section>

    <!-- 危机渠道精简区（底部露出） -->
    <section class="crisis-mini">
      <h3 class="st-section-head">危机渠道</h3>
      <div class="cm-row">
        <span class="cm-name">紧急报警</span>
        <a class="cm-tel numeric touch-target" href="tel:110" :aria-label="'拨打紧急报警 110'">110</a>
      </div>
      <div class="cm-row">
        <span class="cm-name">青少年服务台（共青团热线）</span>
        <a class="cm-tel numeric touch-target" href="tel:12355" :aria-label="'拨打青少年服务台 12355'">12355</a>
      </div>
      <p class="cm-tip">情况紧急请立即拨打以上渠道求助。</p>
    </section>

    <AiDisclaimer ai-label="申诉由人工复核" disclaimer="复核结果不影响已拦截会话的安全记录" />

    <!-- 底部操作区 -->
    <div class="act-dock">
      <el-button size="large" class="submit-btn" :loading="submitting" :disabled="submitted || !sessionId" @click="submit">
        <svg v-if="!submitting" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M5 12h13m0 0-5-5m5 5-5 5" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        {{ submitted ? '申诉已提交' : '提交申诉' }}
      </el-button>
      <el-button size="large" plain class="back-btn" @click="$safeBack()">‹ 返回会话</el-button>
      <p v-if="!sessionId" class="no-session caption">缺少关联会话，无法提交申诉</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createAppeal } from '@/api/client'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

const route = useRoute()

/** 关联会话 uid */
const sessionId = computed(() => (route.query.session as string) || '')

/** 解析 query.data 中的 blocked 详情 */
const blocked = computed<any>(() => {
  try {
    const raw = route.query.data as string
    return raw ? JSON.parse(decodeURIComponent(raw)) : {}
  } catch {
    return {}
  }
})

/**
 * 风险事件编号：优先 query.risk_no，缺省时从 query.data 的 blocked 帧兜底
 * （多字段名兼容 risk_event_no / risk_no / event_no）
 */
const riskEventNo = computed<string>(() => {
  const q = (route.query.risk_no as string) || ''
  if (q) return q
  const d = blocked.value || {}
  return d.risk_event_no || d.risk_no || d.event_no || ''
})

/** 命中参考类别显示名（短标签，不用 reason 长句） */
const riskCategory = computed(() => blocked.value?.risk_category_label || '儿童安全类')

/**
 * 拦截记录编号展示文本（无编号时不造假；编号本身已含 RISK 前缀时不重复拼接）
 */
const riskNoText = computed(() => {
  const v = riskEventNo.value
  if (!v) return '生成中或本次未记录'
  return /^RISK/i.test(v) ? v : `RISK-${v}`
})

/** 申诉说明文本（≤500 字） */
const note = ref('')
/** 提交中 */
const submitting = ref(false)
/** 提交结果 {appeal_no, sla_due_at} */
const result = ref<{ appeal_no: string; sla_due_at: string } | null>(null)
/** 提交错误信息 */
const error = ref('')

/** 是否已提交（按钮置为已提交态） */
const submitted = computed(() => !!result.value)

/**
 * 附件按钮（演示占位：暂无上传通道，提示合规要求）
 */
function onAttach(): void {
  ElMessage.info('图片申诉暂通过客服渠道补充，请先遮盖孩子可识别信息')
}

/**
 * 提交申诉（appeal_note → createAppeal；成功停留本页展示受理编号）
 * @throws 网络失败时内联展示错误
 */
async function submit(): Promise<void> {
  if (!sessionId.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    result.value = await createAppeal({
      session_uid: sessionId.value,
      appeal_note: note.value.trim()
    })
    ElMessage.success('申诉已受理，请留意复核结果')
  } catch (e: any) {
    error.value = e?.message || '提交失败，请稍后重试'
    ElMessage.error(error.value)
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
.appeal-page {
  padding-bottom: 190px;
}

/* 页头 */
.qa-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-2);

  .head-title {
    flex: 1;
    text-align: center;
    font-size: var(--fs-title);
    font-weight: 700;
    color: var(--ink-1);
  }

  .head-btn {
    width: 32px;
    height: 32px;
    border: none;
    background: none;
    color: var(--ink-1);
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;

    svg { width: 20px; height: 20px; }
  }

  .head-spacer { width: 32px; flex: none; }
}

/* 守护模式行 */
.protocol-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-4);

  .pr-label {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-caption);
    color: var(--ink-3);

    .pr-dot {
      width: 6px;
      height: 6px;
      border-radius: 1px;
      background: var(--accent);
    }
  }

  .pr-chip {
    font-size: var(--fs-caption);
    color: var(--warn);
    background: var(--warn-soft);
    border: 1px solid color-mix(in srgb, var(--warn) 30%, transparent);
    border-radius: 4px;
    padding: 1px 8px;
  }
}

/* ===== 拦截卡 ===== */
.block-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-6);
  box-shadow: var(--shadow-e1);
  margin-bottom: var(--sp-4);
}

.bc-head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);

  .bc-ico {
    width: 34px;
    height: 34px;
    border-radius: var(--radius-ctl);
    background: var(--accent-soft);
    color: var(--accent);
    display: flex;
    align-items: center;
    justify-content: center;
    flex: none;

    svg { width: 19px; height: 19px; }
  }

  .bc-title {
    font-size: var(--fs-title);
    font-weight: 700;
    color: var(--ink-1);
  }
}

.bc-desc {
  margin-top: var(--sp-3);
  font-size: var(--fs-sub);
  color: var(--ink-2);
  line-height: 1.7;
}

/* 编号/类别元信息行 */
.bc-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-top: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  border: 1px solid var(--line);

  .bm-label {
    font-size: var(--fs-caption);
    color: var(--ink-3);
    flex: 1;
  }

  .bm-value {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
  }

  .bm-chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    font-size: var(--fs-caption);
    color: var(--accent);
    font-weight: 600;

    .dot {
      width: 6px;
      height: 6px;
      border-radius: 1px;
      background: var(--accent);
    }
  }
}

/* 不展示原文承诺 */
.bc-promise {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--ink-3);
  line-height: 1.7;

  svg { width: 14px; height: 14px; flex: none; margin-top: 3px; color: var(--ink-3); }
}

/* ===== 误报展开卡 ===== */
.mistake-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: 0 var(--sp-6);
  box-shadow: var(--shadow-e1);
  margin-bottom: var(--sp-4);

  summary {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    padding: var(--sp-4) 0;
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
    cursor: pointer;
    list-style: none;

    &::-webkit-details-marker { display: none; }

    .swap { width: 17px; height: 17px; color: var(--accent); }

    .chev {
      margin-left: auto;
      width: 16px;
      height: 16px;
      color: var(--ink-3);
      transition: transform 0.2s;
    }
  }

  &[open] summary .chev {
    transform: rotate(180deg);
  }
}

/* 补充说明表单 */
.note-sec {
  padding-bottom: var(--sp-4);
}

.ns-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-bottom: var(--sp-2);

  strong {
    font-size: var(--fs-sub);
    color: var(--ink-1);
  }

  .ns-count {
    font-size: var(--fs-caption);
    color: var(--ink-3);
  }
}

.ns-textarea {
  width: 100%;
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--ink-1);
  font-family: inherit;
  font-size: var(--fs-sub);
  line-height: 1.6;
  resize: vertical;

  &:focus {
    outline: none;
    border-color: var(--accent);
  }
}

.attach-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--sp-3);
  padding: 8px 14px;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  cursor: pointer;

  svg { width: 15px; height: 15px; }

  &:active { background: var(--surface-2); }
}

.attach-tip {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--warn-soft);
  border: 1px solid color-mix(in srgb, var(--warn) 30%, transparent);
  color: var(--warn);
  font-size: var(--fs-caption);
  line-height: 1.6;

  svg { width: 14px; height: 14px; flex: none; margin-top: 3px; }
}

/* ===== 申诉状态卡 ===== */
.status-card {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-6);
  box-shadow: var(--shadow-e1);
  margin-bottom: var(--sp-4);
}

.sc-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-3);

  .sc-title {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-sub);
    color: var(--ink-1);

    svg { width: 16px; height: 16px; color: var(--accent); }
  }

  .sc-badge {
    font-size: var(--fs-caption);
    color: var(--accent);
    background: var(--accent-soft);
    border: 1px solid var(--accent-line);
    border-radius: var(--radius-pill);
    padding: 2px 10px;
    font-weight: 600;
  }
}

.sc-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-top: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--sc-low);
  border: 1px solid var(--line);

  .bm-label {
    font-size: var(--fs-caption);
    color: var(--ink-3);
    flex: 1;
  }

  .bm-value {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
  }
}

.sc-note {
  margin-top: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  font-size: var(--fs-caption);
  color: var(--ink-3);
  line-height: 1.7;
}

/* ===== 危机渠道精简区 ===== */
.crisis-mini {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-4) var(--sp-6);
  margin-bottom: var(--sp-2);

  .st-section-head {
    margin-bottom: var(--sp-2);
  }
}

.cm-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-2) 0;

  & + .cm-row {
    border-top: 1px dashed var(--line);
  }

  .cm-name {
    font-size: var(--fs-sub);
    color: var(--ink-1);
  }

  .cm-tel {
    font-size: var(--fs-sub);
    font-weight: 700;
    color: var(--danger);
    text-decoration: none;
  }
}

.cm-tip {
  margin-top: var(--sp-2);
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

/* ===== 底部操作区 ===== */
.act-dock {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 430px;
  padding: var(--sp-3) var(--sp-6) calc(var(--sp-2) + env(safe-area-inset-bottom));
  background: var(--surface);
  border-top: 1px solid var(--line);
  z-index: 90;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);

  .el-button {
    width: 100%;
    margin: 0;
  }
}

/* 提交申诉主按钮：品牌深绿 */
.submit-btn {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--on-accent);
  font-weight: 600;
  display: inline-flex;
  align-items: center;
  gap: 6px;

  svg { width: 17px; height: 17px; }

  &:disabled {
    background: var(--surface-2);
    border-color: var(--line);
    color: var(--ink-3);
  }
}

/* 返回会话次按钮 */
.back-btn {
  color: var(--ink-1);
  border-color: var(--line-strong);
  background: var(--surface);
}

.no-session {
  text-align: center;
  color: var(--danger);
}
</style>
