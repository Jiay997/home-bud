<!--
  OrderPage SC-22 订单与支付（Stitch 稿重构）
  页头（‹ 订单与支付）+ 三段进程条（订单确认——支付校验——结果回执）+
  订单确认卡（ORD 编号 chip + 商品/金额/有效期 + 不退款提示 + 立即支付 + 二次核验声明）+
  支付确认中卡（校验通道徽章 + VAL-TOKEN + 幂等防重说明 + 未回调保权益说明）+
  支付成功回执卡（大对勾 + 交易参考号 + 生效/到期双行 + 查看会员内容）+ 失败态保留。
  五态状态机 confirm → paying → verifying → success | failed 与模拟支付签名逻辑全保留。
-->
<template>
  <div class="page op-page">
    <!-- 页头 -->
    <header class="op-head">
      <button class="back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">订单与支付</h1>
    </header>

    <!-- 三段进程条 -->
    <div class="proc-strip">
      <div class="proc-row">
        <template v-for="(s, i) in STEPS" :key="s.key">
          <span class="proc-node" :class="stepState(i)">
            <span class="pn-dot" />
            {{ s.label }}
          </span>
          <span v-if="i < STEPS.length - 1" class="proc-line" :class="{ done: stepState(i) === 'done' && stepState(i + 1) !== 'todo' }" />
        </template>
      </div>
      <p class="proc-caption caption numeric">制段校验 · 节点标注 {{ nodeTime }}</p>
    </div>

    <!-- 状态一：订单确认卡 -->
    <template v-if="phase === 'confirm'">
      <div class="st-card order-card">
        <div class="oc-head">
          <span class="st-section-head">订单确认</span>
          <span class="st-tag st-tag--outline st-tag--plain numeric">标准编号 {{ orderNo || '生成中…' }}</span>
        </div>
        <div class="oc-row">
          <span class="oc-label caption">购买商品</span>
          <span class="oc-val">会员月卡 · 30 天</span>
        </div>
        <div class="oc-row">
          <span class="oc-label caption">支付金额</span>
          <span class="oc-val oc-price numeric">¥19.9<small> 元</small></span>
        </div>
        <div class="oc-row">
          <span class="oc-label caption">服务有效期</span>
          <span class="oc-val">支付成功起 30 天内有效</span>
        </div>
        <p class="oc-lock caption">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M7 11V8a5 5 0 0 1 10 0v3M5.5 11h13a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-13a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
          解锁内容属一批深度数字内容，一经解锁不支付退款
        </p>

        <el-button
          type="primary"
          size="large"
          class="pay-btn"
          :disabled="paying"
          @click="pay"
        >
          立即支付 ¥19.9 元
        </el-button>
        <p class="oc-verify caption">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
          下单前已二次核验服务端当前商品价格
        </p>
        <p v-if="createError" class="err caption">{{ createError }}</p>
      </div>
    </template>

    <!-- 状态四：支付确认中卡 -->
    <template v-else-if="phase === 'verifying'">
      <div class="st-card verify-card">
        <div class="vc-head">
          <span class="st-section-head">支付确认中</span>
          <span class="st-tag st-tag--amber">校验通道已开启</span>
        </div>
        <div class="vc-body">
          <svg class="vc-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <div>
            <p class="vc-title">支付中…请勿重复点击</p>
            <p class="caption numeric vc-token">交易校验号 VAL-{{ txnId || '…' }}</p>
          </div>
        </div>
        <div class="vc-progress">
          <span class="caption">客户端轮询</span>
          <span class="caption">服务端对应幂等防重</span>
        </div>
        <div class="vc-note">
          <p class="caption">
            支付确认中：已扣款但未收到回调时，通道将关闭注资页，系统回调后自动补——保权益不至于丢失。
          </p>
        </div>
        <div class="vc-actions">
          <el-button size="large" @click="onVerifyAck">我知道了</el-button>
          <el-button size="large" type="primary" plain @click="$router.push('/app/member')">查看订单记录</el-button>
        </div>
      </div>
    </template>

    <!-- 状态五：支付成功回执卡 -->
    <template v-else-if="phase === 'success'">
      <div class="st-card receipt-card">
        <div class="rc-head">
          <span class="st-section-head">支付成功回执</span>
          <span class="caption numeric">回执标号 · {{ receiptNo }}</span>
        </div>
        <div class="rc-hero">
          <div class="rc-check">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </div>
          <p class="rc-title">支付成功</p>
          <p class="caption numeric rc-ref">交易参考号：{{ txnId || '—' }}</p>
        </div>
        <div class="rc-rows">
          <div class="rc-row">
            <span class="caption">权益生效时间</span>
            <span class="numeric">{{ paidAtText }}</span>
          </div>
          <div class="rc-row">
            <span class="caption">服务到期时间</span>
            <span class="numeric">{{ expireAtText }}</span>
          </div>
        </div>
        <el-button type="primary" size="large" class="done-btn" @click="$router.replace('/app/member')">
          查看会员内容 →
        </el-button>
      </div>
    </template>

    <!-- 状态五：失败 -->
    <template v-else-if="phase === 'failed'">
      <div class="st-card state-card">
        <div class="state-icon bad">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.75" />
            <path d="M9 9l6 6m0-6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
        </div>
        <p class="state-title bad-text">支付未完成</p>
        <p class="state-text">{{ failReason }}</p>
        <div class="fail-actions">
          <el-button size="large" @click="retryOrder">返回重试</el-button>
          <el-button type="primary" size="large" @click="$router.replace('/app/home')">回到首页</el-button>
        </div>
      </div>
    </template>

    <!-- 状态三：支付中遮罩（快速过渡态） -->
    <div v-if="phase === 'paying'" class="paying-mask">
      <div class="mask-card">
        <svg class="vc-spin" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <p>支付校验通道开启中…</p>
      </div>
    </div>

    <!-- AI 免责条 -->
    <AiDisclaimer ai-label="AI 生成内容" disclaimer="支付与履约说明以服务端商品配置为准" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { createOrder, mockPay, mockPaySign } from '@/api/client'
import { newRequestId } from '@/api/request'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

/** 五态：confirm → paying → verifying → success | failed */
type Phase = 'confirm' | 'paying' | 'verifying' | 'success' | 'failed'

/** 进程条节点配置 */
const STEPS = [
  { key: 'confirm', label: '订单确认' },
  { key: 'verify', label: '支付校验' },
  { key: 'receipt', label: '结果回执' }
]

/** 当前阶段 */
const phase = ref<Phase>('confirm')
/** 订单号 */
const orderNo = ref('')
/** 创建/支付失败原因 */
const failReason = ref('')
const createError = ref('')
/** 连点防重锁 */
const paying = ref(false)
/** 幂等 id（重试复用） */
const requestId = newRequestId()
/** 交易参考号（成功回执展示） */
const txnId = ref('')
/** 支付完成时间戳 */
const paidAt = ref<number>(0)
/** 页面加载时刻（进程条节点标注） */
const mountedAt = ref<number>(Date.now())

/**
 * 进程条节点标注时间（HH:MM）
 * @returns 时间文本
 */
const nodeTime = computed<string>(() => {
  const d = new Date(mountedAt.value)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d.getHours())}:${p(d.getMinutes())}`
})

/**
 * 权益生效时间文本
 * @returns yyyy-MM-dd HH:mm
 */
const paidAtText = computed<string>(() => fmtDateTime(paidAt.value || Date.now()))

/**
 * 服务到期时间文本（生效 + 30 天）
 * @returns yyyy-MM-dd HH:mm
 */
const expireAtText = computed<string>(() => fmtDateTime((paidAt.value || Date.now()) + 30 * 86400000))

/**
 * 回执标号（截取交易号后 6 位）
 * @returns REC-xxxxxx
 */
const receiptNo = computed<string>(() => `REC-${(txnId.value || String(Date.now())).slice(-6)}`)

/**
 * 时间戳格式化
 * @param ts 毫秒时间戳
 * @returns yyyy-MM-dd HH:mm 文本
 */
function fmtDateTime(ts: number): string {
  const d = new Date(ts)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

/**
 * 进程条节点状态：done 已完成 / doing 进行中 / todo 未到
 * @param i 节点序号
 * @returns 状态类名
 */
function stepState(i: number): 'done' | 'doing' | 'todo' {
  const order: Phase[] = ['confirm', 'paying', 'verifying', 'success', 'failed']
  const idx = order.indexOf(phase.value)
  // 节点映射：0=确认(confirm) 1=校验(paying/verifying) 2=回执(success)；failed 时 1/2 节点标红由样式兜底
  const nodeIdx = [0, idx >= 1 && idx <= 2 ? 1 : idx >= 3 ? 2 : -1, idx >= 3 ? 2 : -1]
  if (nodeIdx[i] > i) return 'done'
  if (nodeIdx[i] === i) return 'doing'
  return 'todo'
}

/**
 * 挂载：预生成订单号展示
 * @throws 创建失败落 createError 提示
 */
onMounted(async () => {
  try {
    const res: any = await createOrder({
      product_code: 'member_monthly',
      platform: 'web',
      contract_confirm: true,
      client_request_id: requestId
    })
    orderNo.value = res?.order_no || res?.order_id || ''
  } catch (e: any) {
    createError.value = e?.message || '订单创建失败，请返回重试'
  }
})

/**
 * 发起支付：创建订单已就绪 → 模拟支付 → 校验签名结果
 * 连点防重：paying 锁；阶段推进 confirm → paying → verifying → success/failed
 * @throws 支付失败进入 failed 态（幂等 id 复用保证不重复扣款）
 */
async function pay(): Promise<void> {
  if (paying.value) return
  paying.value = true
  phase.value = 'paying'
  try {
    if (!orderNo.value) {
      const res: any = await createOrder({
        product_code: 'member_monthly',
        platform: 'web',
        contract_confirm: true,
        client_request_id: requestId
      })
      orderNo.value = res?.order_no || res?.order_id || ''
    }
    const transactionId = 'TXN' + Date.now()
    const sign = await mockPaySign(transactionId)
    phase.value = 'verifying'
    await mockPay(orderNo.value, transactionId, sign)
    txnId.value = transactionId
    paidAt.value = Date.now()
    phase.value = 'success'
    ElMessage.success('支付成功')
  } catch (e: any) {
    failReason.value = e?.message || '支付失败，未扣除款项'
    phase.value = 'failed'
  } finally {
    paying.value = false
  }
}

/**
 * 支付确认中"我知道了"：仅提示继续等待（确认中不可离开）
 */
function onVerifyAck(): void {
  ElMessage.info('支付结果确认中，确认完成后将自动进入回执')
}

/**
 * 失败后返回重试（复用同一幂等 id）
 */
function retryOrder(): void {
  phase.value = 'confirm'
  createError.value = ''
}
</script>

<style lang="scss" scoped>
/* ---------- 页头 ---------- */
.op-head {
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
    font-size: var(--fs-title);
    font-weight: 600;
    color: var(--ink-1);
  }
}

/* ---------- 三段进程条 ---------- */
.proc-strip {
  background: var(--surface-2);
  border-radius: var(--radius-face);
  padding: var(--sp-3) var(--sp-4);
  margin-bottom: var(--sp-4);
}

.proc-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.proc-node {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
  white-space: nowrap;

  .pn-dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--line-strong);
    flex: none;
  }

  &.doing {
    color: var(--ink-1);
    font-weight: 600;

    .pn-dot {
      background: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-soft);
    }
  }

  &.done {
    color: var(--accent);

    .pn-dot {
      background: var(--accent);
    }
  }
}

.proc-line {
  flex: 1;
  height: 2px;
  border-radius: 1px;
  background: var(--line-strong);

  &.done {
    background: var(--accent);
  }
}

.proc-caption {
  margin-top: var(--sp-2);
  text-align: right;
  color: var(--ink-3);
}

/* ---------- 订单确认卡 ---------- */
.order-card {
  margin-bottom: var(--sp-4);
}

.oc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-3);
}

.oc-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: var(--sp-3) 0;

  & + .oc-row {
    border-top: 1px dashed var(--line);
  }

  .oc-val {
    font-size: var(--fs-sub);
    color: var(--ink-1);
    font-weight: 500;
  }

  .oc-price {
    font-size: 30px;
    font-weight: 700;
    color: var(--ink-1);

    small {
      font-size: var(--fs-caption);
      font-weight: 400;
      color: var(--ink-3);
    }
  }
}

.oc-lock {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  padding: var(--sp-3) var(--sp-4);
  background: var(--surface-2);
  border-radius: var(--radius-ctl);
  color: var(--ink-3);
  line-height: 1.7;
  margin-bottom: var(--sp-4);

  svg {
    flex: none;
    width: 14px;
    height: 14px;
    margin-top: 3px;
    color: var(--warn);
  }
}

.pay-btn {
  width: 100%;
  height: 48px;
}

.oc-verify {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  margin-top: var(--sp-3);

  svg {
    width: 13px;
    height: 13px;
    color: var(--accent);
  }
}

.err {
  margin-top: var(--sp-3);
  color: var(--danger);
  text-align: center;
}

/* ---------- 支付确认中卡 ---------- */
.verify-card {
  margin-bottom: var(--sp-4);
}

.vc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-3);
}

.vc-body {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-4);
  background: var(--surface-2);
  border-radius: var(--radius-ctl);
  margin-bottom: var(--sp-3);

  .vc-title {
    font-size: var(--fs-body);
    font-weight: 600;
    color: var(--ink-1);
  }

  .vc-token {
    margin-top: 2px;
    color: var(--ink-3);
  }
}

.vc-spin {
  flex: none;
  width: 26px;
  height: 26px;
  color: var(--accent);
  animation: op-rotate 1.1s linear infinite;
}

@keyframes op-rotate {
  to {
    transform: rotate(360deg);
  }
}

.vc-progress {
  display: flex;
  justify-content: space-between;
  color: var(--ink-3);
  margin-bottom: var(--sp-3);
}

.vc-note {
  background: var(--warn-soft);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);
  margin-bottom: var(--sp-4);

  .caption {
    color: var(--ink-2);
    line-height: 1.7;
  }
}

.vc-actions {
  display: flex;
  gap: var(--sp-3);

  .el-button {
    flex: 1;
  }
}

/* ---------- 成功回执卡 ---------- */
.receipt-card {
  margin-bottom: var(--sp-4);
}

.rc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-4);

  > .caption {
    color: var(--ink-3);
  }
}

.rc-hero {
  text-align: center;
  padding: var(--sp-6) 0;

  .rc-check {
    width: 56px;
    height: 56px;
    margin: 0 auto var(--sp-3);
    border-radius: 50%;
    background: var(--accent);
    color: var(--on-accent);
    display: flex;
    align-items: center;
    justify-content: center;

    svg {
      width: 30px;
      height: 30px;
    }
  }

  .rc-title {
    font-size: var(--fs-display);
    font-weight: 700;
    color: var(--ink-1);
  }

  .rc-ref {
    margin-top: var(--sp-2);
    color: var(--ink-3);
  }
}

.rc-rows {
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-2) var(--sp-4);
  margin-bottom: var(--sp-4);

  .rc-row {
    display: flex;
    justify-content: space-between;
    padding: var(--sp-2) 0;
    font-size: var(--fs-sub);
    color: var(--ink-1);

    & + .rc-row {
      border-top: 1px dashed var(--line);
    }

    .caption {
      color: var(--ink-3);
    }
  }
}

.done-btn {
  width: 100%;
  height: 48px;
}

/* ---------- 失败态 ---------- */
.state-card {
  text-align: center;
  padding: var(--sp-10) var(--sp-6);
  margin-bottom: var(--sp-4);
}

.state-icon {
  width: 56px;
  height: 56px;
  margin: 0 auto var(--sp-4);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;

  svg {
    width: 30px;
    height: 30px;
  }

  &.bad {
    background: var(--danger-soft);
    color: var(--danger);
  }
}

.state-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
}

.bad-text {
  color: var(--danger);
}

.state-text {
  margin-top: var(--sp-2);
  font-size: var(--fs-sub);
  color: var(--ink-2);
}

.fail-actions {
  display: flex;
  gap: var(--sp-3);
  margin-top: var(--sp-8);

  .el-button {
    flex: 1;
  }
}

/* ---------- 支付中遮罩 ---------- */
.paying-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 200;
}

.mask-card {
  background: var(--surface);
  border-radius: var(--radius-face);
  padding: var(--sp-6) var(--sp-8);
  text-align: center;
  font-size: var(--fs-sub);
  color: var(--ink-1);
  width: 220px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-3);
}
</style>
