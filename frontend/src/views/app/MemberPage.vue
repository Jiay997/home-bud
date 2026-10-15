<!--
  MemberPage SC-20 会员权益（Stitch 稿重构）
  PageHeader（返回 + 会员权益 + 基础对比 chip + 副标）+ 功能与规格基准对照表（免费/会员 三列）+
  会员月卡卡（标准标签 + ¥19.9/月 + 计费说明三行 + 虚拟内容退款告知勾选——原
  contract_confirm 逻辑保留 + 未勾选置灰 + 支付保障声明）+
  履约状态与凭证卡（当前生效账户 + 内容归属规则）。
  购买入口跳转 OrderPage 五态流程；非会员/会员状态逻辑保留。
  SC-21 额度用尽抽屉已抽为共用组件 QuotaDrawer，由问答页 1202 触发，此处不再内嵌。
-->
<template>
  <div class="page mp-page">
    <!-- 页头 -->
    <PageHeader title="会员权益" sub="解锁深度养育内容 · 答复刻度与成长记录">
      <template #right>
        <span class="st-tag st-tag--gray">基础对比</span>
      </template>
    </PageHeader>

    <!-- 功能与规格基准对照卡 -->
    <div class="st-card cmp-card">
      <div class="cmp-head">
        <span class="st-section-head">功能与规格基准</span>
        <span class="caption">对照标准 v2.4</span>
      </div>
      <div class="cmp-table">
        <div class="cmp-thead caption">
          <span>评估及规划维度</span>
          <span class="ta-c">免费方案</span>
          <span class="ta-c pro">会员方案</span>
        </div>
        <div v-for="row in ROWS" :key="row.name" class="cmp-row">
          <div class="cmp-name">
            <p class="cn-title">{{ row.name }}</p>
            <p class="cn-desc caption">{{ row.desc }}</p>
          </div>
          <span class="ta-c cmp-free caption">{{ row.free }}</span>
          <span class="ta-c cmp-pro">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            {{ row.pro }}
          </span>
        </div>
      </div>
      <p class="cmp-note caption">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 7v5l3 2m-3-13a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
        刻度校准注解：科学喂养分类指南 + 4/4 维度
      </p>
    </div>

    <!-- 会员月卡卡 -->
    <div class="st-card price-card">
      <div class="price-top">
        <div class="price-name">
          <h2 class="pn-title">会员月卡</h2>
          <span class="st-tag st-tag--green st-tag--plain">标准</span>
        </div>
        <p class="price-val"><span class="p-num numeric">¥19.9</span><span class="p-unit">/月</span></p>
      </div>
      <div class="price-attrs">
        <span class="caption">单次购买 · 不自动续费</span>
        <span class="caption">有效期 30 天 · 到期不自动扣费</span>
      </div>

      <!-- 计费说明三行 -->
      <ul class="fee-list">
        <li>
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 7v5l3 2m-3-13a9 9 0 1 1 0 18 9 9 0 0 1 0-18Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
          计费量：到期即止，无需解绑协议
        </li>
        <li>
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12 5 5 9-9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
          价格以服务端商品配置为准，明码公开
        </li>
        <li>
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v4h-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
          单次购买 · 不自动续费
        </li>
      </ul>

      <!-- 虚拟内容退款告知勾选（合规必须，原 contract_confirm） -->
      <label class="refund-row">
        <el-checkbox v-model="refundAgreed" />
        <span>虚拟内容一经解锁不支持退款，我已阅读并知悉上述说明</span>
      </label>

      <el-button
        type="primary"
        size="large"
        class="buy-btn"
        :disabled="!refundAgreed || user.isMember"
        @click="$router.push('/app/member/order')"
      >
        {{ user.isMember ? '已是会员 · 查看状态' : `立即开通 19.9 元` }}
      </el-button>
      <p v-if="!refundAgreed && !user.isMember" class="buy-hint caption">未勾选说明前按钮置灰，勾选后方可开通</p>
      <p class="pay-secure caption">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
        微信支付安全保障 · 支付流程由模拟支付完成
      </p>
    </div>

    <!-- 履约状态与凭证卡 -->
    <div class="st-card fulfill-card">
      <div class="ful-head">
        <span class="st-section-head">履约状态与凭证</span>
        <div class="ful-links caption">
          <a class="ful-link" @click.prevent="$router.push('/app/member/order')">订单记录</a>
          <a class="ful-link" @click.prevent="ElMessage.info('权益说明：以服务端商品配置与履约凭证为准')">权益说明</a>
        </div>
      </div>

      <!-- 当前生效账户卡 -->
      <div class="account-card">
        <div class="ac-row">
          <span class="caption">当前生效账户</span>
          <span class="caption">截止日期</span>
        </div>
        <div class="ac-row ac-main">
          <p class="ac-status">
            会员状态：<strong :class="user.isMember ? 'ok' : 'dim'">{{ user.isMember ? '有效' : '未开通' }}</strong>
          </p>
          <p class="ac-expire numeric">{{ expireText }}</p>
        </div>
      </div>

      <!-- 内容归属规则说明块 -->
      <div class="rule-block">
        <p class="rb-title">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h7L18 8.5V19a1 1 0 0 1-1 1H6.5A2.5 2.5 0 0 1 4 17.5v-11Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
          内容归属规则
        </p>
        <p class="rb-body">
          会员到期：深度内容保留只读（不可新增、可线性查看），已生成的健康评估与刻度报告永久免费阅览。
        </p>
      </div>
    </div>

    <!-- AI 免责条 -->
    <AiDisclaimer ai-label="AI 生成内容" disclaimer="仅供养育参考，不替代医生诊断" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getSubscription } from '@/api/client'
import { useUserStore } from '@/stores/user'
import AiDisclaimer from '@/components/AiDisclaimer.vue'
import PageHeader from '@/components/PageHeader.vue'

const user = useUserStore()

/** 退款告知勾选（原 contract_confirm 语义保留） */
const refundAgreed = ref(false)

/** 会员到期时间（来自订阅接口，拿不到时展示占位） */
const expireAt = ref<string>('')

/** 权益对照行（评估及规划维度 / 免费方案 / 会员方案） */
const ROWS = [
  { name: '深度养育方案', desc: '多智能体动态与精细评估', free: '无', pro: '有' },
  { name: '月度养育计划', desc: '阶段发育目标与执行日历', free: '无', pro: '有' },
  { name: '宠物长期规划', desc: '全生命周期健康管理照护谱', free: '无', pro: '有' },
  { name: '复合场景策略', desc: '多重现场，换季与应急筹备', free: '部分', pro: '完整' }
]

/**
 * 到期日期展示文本
 * @returns yyyy-MM-dd 或占位符
 */
const expireText = computed<string>(() => {
  if (!expireAt.value) return user.isMember ? '以履约凭证为准' : '开通后顺延 30 天'
  const d = new Date(expireAt.value)
  if (isNaN(d.getTime())) return expireAt.value
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
})

/**
 * 挂载：刷新用户态 + 拉取订阅履约信息
 * @throws 订阅接口失败静默（保留占位文案）
 */
onMounted(async () => {
  user.refreshQuota()
  user.refreshMe()
  try {
    const sub: any = await getSubscription()
    // SIM-22 修复：订阅接口包络 data 为 {member_status, member_expire_at, subscription}，
    // 实际到期日在 data.member_expire_at（用户表口径）或 data.subscription.expire_at
    // （订阅表口径），此前误取 data.expire_at 顶层字段导致恒为空回显「以履约凭证为准」
    expireAt.value =
      sub?.member_expire_at || sub?.subscription?.expire_at || sub?.current_period_end || sub?.expired_at || ''
  } catch {
    // 静默：非会员或未订阅时保留占位展示
  }
})
</script>

<style lang="scss" scoped>
/* ---------- 对照卡 ---------- */
.cmp-card,
.price-card,
.fulfill-card {
  margin-bottom: var(--sp-4);
}

.cmp-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-3);

  > .caption {
    color: var(--ink-3);
  }
}

.ta-c {
  text-align: center;
}

.cmp-thead {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr 0.8fr;
  gap: var(--sp-2);
  padding-bottom: var(--sp-2);
  color: var(--ink-3);

  .pro {
    color: var(--accent);
    font-weight: 600;
  }
}

.cmp-row {
  display: grid;
  grid-template-columns: 1.4fr 0.8fr 0.8fr;
  gap: var(--sp-2);
  align-items: center;
  padding: var(--sp-3) 0;
  border-top: 1px dashed var(--line);

  .cn-title {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
  }

  .cn-desc {
    margin-top: 1px;
  }

  .cmp-free {
    color: var(--ink-3);
  }

  .cmp-pro {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 3px;
    color: var(--accent);
    font-weight: 600;
    font-size: var(--fs-caption);

    svg { width: 14px; height: 14px; }
  }
}

.cmp-note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--line);
  color: var(--ink-3);

  svg {
    width: 14px;
    height: 14px;
    color: var(--accent);
  }
}

/* ---------- 价格卡 ---------- */
.price-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--sp-2);

  .price-name {
    display: flex;
    align-items: center;
    gap: var(--sp-2);

    .pn-title {
      font-size: var(--fs-title);
      font-weight: 600;
      color: var(--ink-1);
    }
  }

  .price-val {
    .p-num {
      font-size: 28px;
      font-weight: 700;
      color: var(--ink-1);
    }

    .p-unit {
      font-size: var(--fs-caption);
      color: var(--ink-3);
      margin-left: 2px;
    }
  }
}

.price-attrs {
  display: flex;
  gap: var(--sp-4);
  color: var(--ink-3);
  margin-bottom: var(--sp-3);
}

.fee-list {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-4);
  background: var(--surface-2);
  border-radius: var(--radius-ctl);
  margin-bottom: var(--sp-4);

  li {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-caption);
    color: var(--ink-2);
  }

  svg {
    width: 14px;
    height: 14px;
    color: var(--accent);
    flex-shrink: 0;
  }
}

.refund-row {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  text-align: left;
  /* 勾选行触控下限：DESIGN.md 主操作 ≥44px */
  min-height: var(--touch-min);
  padding: var(--sp-2) 0;
  margin-bottom: var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.6;
  cursor: pointer;
}

.buy-btn {
  width: 100%;
  height: 48px;
}

.buy-hint {
  margin-top: var(--sp-3);
  text-align: center;
}

.pay-secure {
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

/* ---------- 履约卡 ---------- */
.ful-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-3);

  .ful-links {
    display: flex;
    gap: var(--sp-3);
  }

  .ful-link {
    color: var(--accent);
    text-decoration: underline;
    cursor: pointer;
  }
}

.account-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);
  margin-bottom: var(--sp-3);

  .ac-row {
    display: flex;
    justify-content: space-between;
    color: var(--ink-3);
  }

  .ac-main {
    margin-top: var(--sp-2);
    align-items: baseline;

    .ac-status {
      font-size: var(--fs-sub);
      color: var(--ink-2);

      strong.ok {
        color: var(--accent);
        font-size: var(--fs-title);
      }

      strong.dim {
        color: var(--ink-3);
        font-size: var(--fs-title);
      }
    }

    .ac-expire {
      font-size: var(--fs-sub);
      font-weight: 600;
      color: var(--ink-1);
    }
  }
}

.rule-block {
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);

  .rb-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
    margin-bottom: var(--sp-2);

    svg {
      width: 15px;
      height: 15px;
      color: var(--accent);
    }
  }

  .rb-body {
    font-size: var(--fs-caption);
    color: var(--ink-2);
    line-height: 1.7;
  }
}
</style>
