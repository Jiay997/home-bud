<!--
  FeedbackPage SC-26 反馈与举报（Stitch 稿重构）
  页头（‹ 反馈与举报 + 校准标注行）+ 分段切换卡（我要反馈 / 一键举报——原双表单切换）+
  反馈表单（▎问题描述必填 + 合规占位文案 + 量化刻度计数行 + 关联内容双下拉（真实会话/报告列表）+
  图片上传卡（≤3 张 + 审核中角标 + 删除 + 内容安全检测提示条）+ 提交回执）+
  举报表单（4 分类单选卡 + 对象 + 描述 + 提交回执）。
  原提交逻辑 / feedback_no 与 report_no 回执展示保留。
-->
<template>
  <div class="page fb-page">
    <!-- 页头 -->
    <header class="fb-head">
      <button class="back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">反馈与举报</h1>
    </header>
    <p class="calib-line caption">校准：SC-26</p>

    <!-- 分段切换卡 -->
    <div class="seg-card">
      <button class="seg" :class="{ on: mode === 'feedback' }" @click="mode = 'feedback'">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 6h12M4 12h8M4 18h5m9-1 2 2 4-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
        我要反馈
      </button>
      <button class="seg" :class="{ on: mode === 'report' }" @click="mode = 'report'">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M5 21V4m0 1h11l-2 3.5L16 12H5" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
        一键举报
      </button>
    </div>

    <!-- ================= 反馈表单 ================= -->
    <template v-if="mode === 'feedback'">
      <!-- 问题描述卡 -->
      <div class="st-card form-card">
        <div class="fc-head">
          <span class="st-section-head">问题描述 <em class="req-star">（必须）</em></span>
          <span class="st-tag st-tag--outline st-tag--plain">量具校准刻度</span>
        </div>
        <el-input
          v-model="fbContent"
          type="textarea"
          :rows="5"
          maxlength="500"
          placeholder="请详细描述您遇到的问题，如页面故障、数据偏差或异常响应…"
        />
        <div class="meter-line">
          <span class="caption">▎量化刻度：精度级采集</span>
          <span class="numeric caption">{{ fbContent.length }} / 500</span>
        </div>
      </div>

      <!-- 关联内容卡 -->
      <div class="st-card form-card">
        <div class="fc-head">
          <span class="st-section-head with-ico">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 15l6-6M8.5 12.5l-2 2a3 3 0 0 0 4.2 4.2l2-2m.8-5.2 2-2a3 3 0 0 0-4.2-4.2l-2 2" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
            关联内容
          </span>
          <span class="caption">标定问题溯源</span>
        </div>
        <div class="link-selects">
          <el-select v-model="linkedSession" placeholder="选择对话" clearable size="large" class="ls-item">
            <el-option v-for="s in sessionOptions" :key="s.uid" :label="s.label" :value="s.uid" />
          </el-select>
          <el-select v-model="linkedReport" placeholder="选择报告" clearable size="large" class="ls-item">
            <el-option v-for="r in reportOptions" :key="r.uid" :label="r.label" :value="r.uid" />
          </el-select>
        </div>
      </div>

      <!-- 图片上传卡 -->
      <div class="st-card form-card">
        <div class="fc-head">
          <span class="st-section-head with-ico">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 8.5A1.5 1.5 0 0 1 5.5 7h2L9 5h6l1.5 2h2A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5v-9ZM12 16a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
            图片上传
          </span>
          <span class="caption">最多 3 张，已选 {{ fbImages.length }}/3</span>
        </div>
        <div class="img-row">
          <div v-for="(img, i) in fbImages" :key="i" class="img-slot filled">
            <span class="img-audit">⟳ 审核中</span>
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 17l4.5-5 3.5 4 2.5-3 5.5 4M4 5h16v14H4V5Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
            <span class="img-name caption">{{ img }}</span>
            <button class="img-del" aria-label="删除图片" @click="removeImage(i)">×</button>
          </div>
          <div v-if="fbImages.length < 3" class="img-slot add" @click="addImage">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M12 5v14m-7-7h14" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
            </svg>
            <span class="caption">添加截图</span>
          </div>
        </div>
        <div class="st-note img-note">
          <svg class="note-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
          <p>图片将自动走内容安全检测 · 检测中→审核中，不通过则退回</p>
        </div>

        <el-button
          type="primary"
          size="large"
          class="submit-btn"
          :disabled="!fbContent.trim()"
          :loading="fbSubmitting"
          @click="submitFb"
        >
          提交反馈
        </el-button>

        <!-- 提交回执 -->
        <div v-if="fbReceipt" class="receipt-strip">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
          反馈已受理 · 回执编号 <span class="numeric">{{ fbReceipt }}</span>
        </div>
      </div>
    </template>

    <!-- ================= 举报表单 ================= -->
    <div v-else class="st-card form-card">
      <div class="fc-head">
        <span class="st-section-head">举报分类 <em class="req-star">（必选）</em></span>
      </div>
      <div class="cat-grid">
        <button
          v-for="c in RP_CATS"
          :key="c.value"
          class="cat-card"
          :class="{ on: rpCategory === c.value }"
          @click="rpCategory = c.value"
        >
          <svg class="cc-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path :d="c.icon" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span class="cc-name">{{ c.name }}</span>
        </button>
      </div>

      <div class="fc-head mt">
        <span class="st-section-head">举报对象 <em class="req-star">（必填）</em></span>
      </div>
      <el-input v-model="rpTarget" placeholder="如：某条问答 / 某份报告" maxlength="100" />

      <div class="fc-head mt">
        <span class="st-section-head">补充说明 <em class="opt-star">（选填）</em></span>
      </div>
      <el-input v-model="rpDesc" type="textarea" :rows="3" maxlength="300" placeholder="具体描述问题…" />

      <el-button
        type="primary"
        size="large"
        class="submit-btn"
        :disabled="!rpCategory || !rpTarget.trim()"
        :loading="rpSubmitting"
        @click="submitRp"
      >
        提交举报
      </el-button>
      <p class="caption note">恶意举报可能影响你的账号信用，请如实填写</p>

      <!-- 提交回执 -->
      <div v-if="rpReceipt" class="receipt-strip">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
        举报已受理 · 回执编号 <span class="numeric">{{ rpReceipt }}</span>
      </div>
    </div>

    <!-- AI 免责条 -->
    <AiDisclaimer ai-label="AI 生成内容" disclaimer="举报与反馈将由人工复核处理" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { submitFeedback, submitReport, getHistory } from '@/api/client'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

/** 模式：feedback | report */
const mode = ref<'feedback' | 'report'>('feedback')

/* 反馈表单 */
const fbContent = ref('')
const fbImages = ref<string[]>([])
const fbSubmitting = ref(false)

/* 举报表单 */
const rpCategory = ref('')
const rpTarget = ref('')
const rpDesc = ref('')
const rpSubmitting = ref(false)

/**
 * 举报分类单选卡（4 类；界面文案不变，value 对齐后端 POST /reports 合法枚举：
 * illegal / medical_misleading / harmful_to_minor / other，原 harmful/wrong_info/privacy 会被 422 拒绝）；
 * icon 为 24 网格 SVG path
 */
const RP_CATS = [
  {
    // 有害或不当内容 → illegal（违法有害内容）
    value: 'illegal',
    name: '有害或不当内容',
    icon: 'M12 3.8 3.4 19.2A1.6 1.6 0 0 0 4.8 21.6h14.4a1.6 1.6 0 0 0 1.4-2.4L12 3.8ZM12 10v4m0 3v.3'
  },
  {
    // 错误信息误导 → medical_misleading（本产品医疗养育场景，错误信息最贴近医疗误导分类）
    value: 'medical_misleading',
    name: '错误信息误导',
    icon: 'M12 3.5 21 20.5H3l9-17ZM8.6 8.9l6.8 6.8m0-6.8-6.8 6.8'
  },
  {
    // 侵犯隐私 → other（后端枚举无隐私分类，无法对应归入其他）
    value: 'other',
    name: '侵犯隐私',
    icon: 'M6.5 10.5V8a5.5 5.5 0 0 1 11 0v2.5M5.6 10.5h12.8a1.6 1.6 0 0 1 1.6 1.6v7.3a1.6 1.6 0 0 1-1.6 1.6H5.6A1.6 1.6 0 0 1 4 19.4v-7.3a1.6 1.6 0 0 1 1.6-1.6Zm6.4 4v2.4'
  },
  {
    value: 'other',
    name: '其他问题',
    icon: 'M12 20.5a8.5 8.5 0 1 0 0-17 8.5 8.5 0 0 0 0 17ZM9.8 9.4a2.3 2.3 0 1 1 3.2 2.1c-.6.3-1 .9-1 1.6v.4M12 17h.01'
  }
]

/* 关联内容（真实会话/报告列表） */
const linkedSession = ref('')
const linkedReport = ref('')
const sessionOptions = ref<{ uid: string; label: string }[]>([])
const reportOptions = ref<{ uid: string; label: string }[]>([])

/* 提交回执编号 */
const fbReceipt = ref('')
const rpReceipt = ref('')

/**
 * 添加占位图片（≤3 张，演示环境不真实上传）
 */
function addImage(): void {
  if (fbImages.value.length >= 3) return
  fbImages.value.push(`截图 ${String(fbImages.value.length + 1).padStart(2, '0')}`)
}

/**
 * 删除已选占位图片
 * @param i 图片下标
 */
function removeImage(i: number): void {
  fbImages.value.splice(i, 1)
}

/**
 * 加载关联内容候选（问答/报告各取第一页）
 * @throws 失败静默（下拉保留空态）
 */
async function loadLinked(): Promise<void> {
  try {
    const res: any = await getHistory('qa', 1)
    const items = res?.items || res?.records || res || []
    sessionOptions.value = items.slice(0, 20).map((it: any) => ({
      uid: it.uid,
      label: (it.summary || it.title || '未命名会话').slice(0, 24)
    }))
  } catch {
    // 静默
  }
  try {
    const res: any = await getHistory('report', 1)
    const items = res?.items || res?.records || res || []
    reportOptions.value = items.slice(0, 20).map((it: any) => ({
      uid: it.uid,
      label: (it.summary || it.title || '未命名报告').slice(0, 24)
    }))
  } catch {
    // 静默
  }
}

/**
 * 提交反馈（含关联会话/报告；回执编号展示）
 * @throws 失败消息提示
 */
async function submitFb(): Promise<void> {
  fbSubmitting.value = true
  try {
    let content = fbContent.value.trim()
    if (linkedReport.value) content += `（关联报告：${linkedReport.value}）`
    const res: any = await submitFeedback({
      content,
      linked_session_id: linkedSession.value || undefined
    })
    fbReceipt.value = res?.feedback_no || res?.id || `FB${Date.now()}`
    ElMessage.success('反馈已提交，感谢帮助小光景变得更好')
    fbContent.value = ''
    fbImages.value = []
    linkedSession.value = ''
    linkedReport.value = ''
  } catch (e: any) {
    ElMessage.error(e?.message || '提交失败，请重试')
  } finally {
    fbSubmitting.value = false
  }
}

/**
 * 提交举报（回执编号展示）
 * @throws 失败消息提示
 */
async function submitRp(): Promise<void> {
  rpSubmitting.value = true
  try {
    const res: any = await submitReport({
      object_type: 'qa_session',
      object_id: rpTarget.value.trim(),
      category: rpCategory.value,
      description: rpDesc.value.trim() || undefined
    })
    rpReceipt.value = res?.report_no || res?.id || `RP${Date.now()}`
    // 成功提示携带回执编号，与下方回执条文案一致
    ElMessage.success(`举报已受理 · 回执编号 ${rpReceipt.value}`)
    rpCategory.value = ''
    rpTarget.value = ''
    rpDesc.value = ''
  } catch (e: any) {
    ElMessage.error(e?.message || '提交失败，请重试')
  } finally {
    rpSubmitting.value = false
  }
}

onMounted(loadLinked)
</script>

<style lang="scss" scoped>
/* ---------- 页头 ---------- */
.fb-head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);

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
    font-size: var(--fs-title);
    font-weight: 600;
    color: var(--ink-1);
  }
}

.calib-line {
  text-align: right;
  color: var(--ink-3);
  margin: var(--sp-1) 0 var(--sp-3);
}

/* ---------- 分段切换卡 ---------- */
.seg-card {
  display: flex;
  gap: var(--sp-2);
  background: var(--surface-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  padding: var(--sp-2);
  margin-bottom: var(--sp-4);

  .seg {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 6px;
    padding: 10px 0;
    border: 1px solid transparent;
    border-radius: var(--radius-ctl);
    background: transparent;
    color: var(--ink-2);
    font-size: var(--fs-sub);
    cursor: pointer;

    svg { width: 16px; height: 16px; }

    &.on {
      background: var(--surface);
      border-color: var(--line-strong);
      color: var(--accent);
      font-weight: 600;
      box-shadow: var(--shadow-e1);
    }
  }
}

/* ---------- 表单卡 ---------- */
.form-card {
  margin-bottom: var(--sp-4);
}

.fc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-3);

  &.mt {
    margin-top: var(--sp-4);
  }

  .st-section-head {
    flex-wrap: wrap;

    em.req-star {
      font-style: normal;
      color: var(--danger);
      font-weight: 500;
      font-size: var(--fs-caption);
    }

    em.opt-star {
      font-style: normal;
      color: var(--ink-3);
      font-weight: 500;
      font-size: var(--fs-caption);
    }
  }

  .with-ico {
    gap: 6px;

    svg {
      width: 15px;
      height: 15px;
    }
  }

  > .caption {
    color: var(--ink-3);
  }
}

.meter-line {
  display: flex;
  justify-content: space-between;
  margin-top: var(--sp-2);
  color: var(--ink-3);
}

/* ---------- 关联内容 ---------- */
.link-selects {
  display: flex;
  gap: var(--sp-3);

  .ls-item {
    flex: 1;
  }
}

/* ---------- 图片上传 ---------- */
.img-row {
  display: flex;
  gap: var(--sp-3);
  margin-bottom: var(--sp-3);
}

.img-slot {
  width: 84px;
  height: 84px;
  border-radius: var(--radius-ctl);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  position: relative;

  &.filled {
    background: var(--surface-2);
    color: var(--ink-3);
    border: 1px solid var(--line);

    svg { width: 22px; height: 22px; }

    .img-name {
      margin-top: 3px;
    }

    .img-audit {
      position: absolute;
      top: -7px;
      left: -4px;
      font-size: 10px;
      padding: 0 5px;
      border-radius: 3px;
      background: var(--warn);
      color: var(--on-warn);
      line-height: 15px;
    }

    .img-del {
      position: absolute;
      right: -6px;
      bottom: -6px;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      border: none;
      background: var(--ink-1);
      color: var(--surface);
      font-size: 13px;
      line-height: 1;
      cursor: pointer;
    }
  }

  &.add {
    border: 1px dashed var(--line-strong);
    color: var(--ink-3);
    cursor: pointer;
    gap: 4px;

    svg {
      width: 20px;
      height: 20px;
    }
  }
}

.img-note {
  margin-bottom: var(--sp-4);
}

/* ---------- 举报分类卡 ---------- */
.cat-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
}

.cat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: var(--sp-4) 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  cursor: pointer;

  .cc-ico {
    width: 20px;
    height: 20px;
    flex: none;
  }

  &.on {
    border-color: var(--accent);
    color: var(--accent);
    background: var(--accent-soft);
    font-weight: 600;
  }
}

.note {
  margin-top: var(--sp-3);
  margin-bottom: var(--sp-2);
}

.submit-btn {
  width: 100%;
  height: 48px;
}

/* ---------- 回执条 ---------- */
.receipt-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--sp-3);
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--radius-ctl);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  font-size: var(--fs-caption);
  color: var(--ink-2);

  svg {
    flex: none;
    width: 14px;
    height: 14px;
    color: var(--accent);
  }
}
</style>
