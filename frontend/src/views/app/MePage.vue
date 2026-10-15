<!--
  MePage SC-23 个人中心（Stitch 稿重构）
  页头（我的 + 刻度档案室副标）+ 家长用户卡（头像 + 编辑 + 会员横幅 + 编号 + 合规声明）+
  分组列表卡（档案管理 / 历史与互动 / 会员服务 / 个人信息权利 / 协议与合规 / 账号与安全）+
  AI 免责绿条。档案计数（孩子/宠物）与历史份数取真实接口数据；跳转关系全保留。
-->
<template>
  <div class="page me-page">
    <!-- 页头 -->
    <header class="me-head">
      <div class="mh-line">
        <h1 class="page-title">我的</h1>
      </div>
      <button class="mh-more touch-target" type="button" aria-label="账号与安全" @click="$router.push('/app/me/security')">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <circle cx="12" cy="5" r="1.4" fill="currentColor" />
          <circle cx="12" cy="12" r="1.4" fill="currentColor" />
          <circle cx="12" cy="19" r="1.4" fill="currentColor" />
        </svg>
      </button>
    </header>

    <!-- 家长用户卡 -->
    <div class="st-card user-card">
      <div class="uc-top">
        <div class="uc-avatar" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20.5a7.5 7.5 0 0 1 15 0" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
        </div>
        <div class="uc-info">
          <p class="uc-name">家长用户 <button class="uc-edit touch-target" @click="$router.push('/app/me/security')">编辑</button></p>
          <p class="uc-member-banner">
            <span class="dot" aria-hidden="true" />
            <template v-if="user.isMember">会员：有效期至 {{ expireText }}</template>
            <template v-else>免费版 · <a class="uc-open" @click.prevent="$router.push('/app/member')">去开通</a></template>
          </p>
        </div>
      </div>
      <div class="uc-bottom caption">
        <span class="numeric">编号：#CL-{{ uidShort }}</span>
        <span class="uc-pledge">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
          实名与伦理双校准已生效
        </span>
      </div>
    </div>

    <!-- 组一：档案管理 -->
    <div class="st-card group">
      <div class="g-head">
        <span class="st-section-head">档案管理</span>
        <span class="caption">刻度容量：{{ childCount + petCount }}/6</span>
      </div>
      <router-link class="row" to="/app/profiles">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20.5a7.5 7.5 0 0 1 15 0" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
        <span class="row-name">孩子档案</span>
        <span class="st-kpi">{{ childCount }}/3</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </router-link>
      <router-link class="row" to="/app/profiles">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 21s-7-4.6-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.4-7 10-7 10Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
        <span class="row-name">宠物档案</span>
        <span class="st-kpi">{{ petCount }}/3</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </router-link>
    </div>

    <!-- 组二：历史与互动 -->
    <div class="st-card group">
      <div class="g-head">
        <span class="st-section-head">历史与互动</span>
        <span class="caption">同步追踪</span>
      </div>
      <router-link class="row" to="/app/history">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h7L18 8.5V19a1 1 0 0 1-1 1H6.5A2.5 2.5 0 0 1 4 17.5v-11ZM13.5 4v4.5H18" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
        <span class="row-name">历史问答与报告</span>
        <span class="row-tail caption">共 {{ historyCount }} 份 详情</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </router-link>
      <router-link class="row" to="/app/me/feedback">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 5h16v11H8l-4 4V5Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
        <span class="row-name">我的反馈记录</span>
        <span class="row-tail caption">处理完毕</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </router-link>
    </div>

    <!-- 组三：会员服务 -->
    <div class="st-card group">
      <div class="g-head">
        <span class="st-section-head">会员服务</span>
        <span class="caption">凭证与交易</span>
      </div>
      <router-link class="row" to="/app/member">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 9l8-5 8 5-8 5-8-5Zm0 5.5 8 5 8-5" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
        <div class="row-main">
          <span class="row-name">会员与订单</span>
          <span class="row-sub caption">权益 · 订单记录 · 退款政策</span>
        </div>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </router-link>
    </div>

    <!-- 组四：个人信息权利 -->
    <div class="st-card group">
      <div class="g-head">
        <span class="st-section-head">个人信息权利</span>
        <span class="caption">自主可控</span>
      </div>
      <router-link class="row" to="/app/me/rights">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm-3 9h6m-3-3v6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
        <span class="row-name">个人信息权利中心</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </router-link>
      <router-link class="row" to="/app/me/rights">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20.5a7.5 7.5 0 0 1 15 0" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
        <span class="row-name">儿童信息处理规则</span>
        <span class="st-tag st-tag--green st-tag--plain">特别版</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </router-link>
      <div class="row" @click.prevent>
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M8 12h8m-8-4h8m-8 8h5M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
        <span class="row-name">第三方共享清单</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </div>
    </div>

    <!-- 组五：协议与合规 -->
    <div class="st-card group">
      <div class="g-head">
        <span class="st-section-head">协议与合规</span>
        <span class="caption">国家标准合规</span>
      </div>
      <div class="row" @click.prevent>
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M8 12h8m-8-4h8m-8 8h5M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" /></svg>
        <span class="row-name">用户协议 · 隐私政策 · 免责声明</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </div>
      <div class="row" @click.prevent>
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
        <span class="row-name">AI 生成内容标识说明</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </div>
    </div>

    <!-- 组六：账号与安全 -->
    <div class="st-card group">
      <div class="g-head">
        <span class="st-section-head">账号与安全</span>
      </div>
      <router-link class="row" to="/app/me/security">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
        <span class="row-name">账号与安全</span>
        <span class="row-tail caption">设备守护中</span>
        <svg class="chev" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m9 6 6 6-6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      </router-link>
    </div>

    <!-- 深浅模式切换（功能保留，弱化呈现） -->
    <div class="st-card group">
      <div class="row no-border" @click="theme.toggle()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
        </svg>
        <span class="row-name">深色模式</span>
        <el-switch :model-value="theme.isDark" />
      </div>
    </div>

    <!-- AI 免责绿条 -->
    <div class="st-note me-note">
      <svg class="note-ico" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
      <p><strong>AI 生成内容，仅供参考，不替代医生诊断</strong><br />刻度体系基于儿童发育量表与兽医照护规范模型</p>
    </div>

    <p class="ver caption">小光景 · v0.1.0</p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getMe, getChildren, getPets, getHistory, getSubscription } from '@/api/client'
import { useUserStore } from '@/stores/user'
import { useThemeStore } from '@/stores/theme'

const user = useUserStore()
const theme = useThemeStore()

/** 孩子档案数 */
const childCount = ref(0)
/** 宠物档案数 */
const petCount = ref(0)
/** 历史问答与报告总份数 */
const historyCount = ref(0)
/** 会员到期原始时间（来自 /me 扩展字段，可为空） */
const memberExpire = ref<string>('')

/** 用户编号展示：user_uid 前 8 位大写 */
const uidShort = computed<string>(() => (user.userUid || '00000000').slice(0, 8).toUpperCase())

/**
 * 会员到期展示文本
 * @returns yyyy-MM-dd 或占位
 */
const expireText = computed<string>(() => {
  if (memberExpire.value) {
    const d = new Date(memberExpire.value)
    if (!isNaN(d.getTime())) {
      const p = (n: number) => String(n).padStart(2, '0')
      return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
    }
    return memberExpire.value
  }
  return '以履约凭证为准'
})

/**
 * 挂载：刷新用户态 + 拉取档案计数与历史份数
 * @throws 各接口失败静默（计数保留 0，空态由子页兜底）
 */
onMounted(async () => {
  user.refreshQuota()
  user.refreshMe()
  try {
    const me: any = await getMe()
    memberExpire.value = me?.member_expire || me?.member_expired_at || me?.expire_at || ''
  } catch {
    // 静默：到期时间缺失时展示占位
  }
  try {
    // 占位文案收尾（评估 2026-10-12）：订阅接口为权威到期源（与 MemberPage
    // SIM-22 修复同口径），覆盖 getMe 可能缺失的字段——「我的」页同样回显
    // 实际到期日，不再恒显示「以履约凭证为准」
    const sub: any = await getSubscription()
    memberExpire.value =
      sub?.member_expire_at || sub?.subscription?.expire_at || sub?.current_period_end || sub?.expired_at || memberExpire.value
  } catch {
    // 静默：订阅接口失败时保留 getMe 结果或占位
  }
  try {
    const children = await getChildren()
    childCount.value = Array.isArray(children) ? children.length : (children as any)?.items?.length || 0
  } catch {
    // 静默
  }
  try {
    const pets = await getPets()
    petCount.value = Array.isArray(pets) ? pets.length : (pets as any)?.items?.length || 0
  } catch {
    // 静默
  }
  try {
    const res: any = await getHistory('all', 1)
    historyCount.value = res?.total ?? (res?.items || res?.records || res || []).length
  } catch {
    // 静默
  }
})
</script>

<style lang="scss" scoped>
/* ---------- 页头 ---------- */
.me-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-4);

  .mh-line {
    display: flex;
    align-items: baseline;
    gap: var(--sp-2);
  }

  .mh-more {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    padding: 0;
    border: none;
    background: transparent;
    color: var(--ink-3);
    cursor: pointer;

    svg {
      width: 18px;
      height: 18px;
    }
  }
}

/* ---------- 用户卡 ---------- */
.user-card {
  margin-bottom: var(--sp-4);
}

.uc-top {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  margin-bottom: var(--sp-3);
}

.uc-avatar {
  flex: none;
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--surface-2);
  border: 1px solid var(--line);
  color: var(--ink-3);
  display: flex;
  align-items: center;
  justify-content: center;

  svg {
    width: 28px;
    height: 28px;
  }
}

.uc-name {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);

  .uc-edit {
    border: 1px solid var(--line-strong);
    background: var(--surface);
    color: var(--ink-2);
    font-size: var(--fs-caption);
    padding: 1px 10px;
    border-radius: var(--radius-pill);
    cursor: pointer;
  }
}

.uc-member-banner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-top: var(--sp-2);
  padding: 3px 12px;
  border-radius: var(--radius-pill);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  font-size: var(--fs-caption);
  color: var(--ink-2);

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: var(--accent);
  }

  .uc-open {
    color: var(--accent);
    font-weight: 600;
    cursor: pointer;
  }
}

.uc-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-top: 1px dashed var(--line);
  padding-top: var(--sp-3);
  color: var(--ink-3);

  .uc-pledge {
    display: inline-flex;
    align-items: center;
    gap: 4px;

    svg {
      width: 13px;
      height: 13px;
      color: var(--accent);
    }
  }
}

/* ---------- 分组列表 ---------- */
.group {
  margin-bottom: var(--sp-4);
  padding: var(--sp-4) var(--sp-6);
}

.g-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-2);

  > .caption {
    color: var(--ink-3);
  }
}

.row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  /* 列表行触控下限：DESIGN.md 主操作 ≥44px */
  min-height: var(--touch-min);
  text-decoration: none;
  color: var(--ink-1);
  border-top: 1px dashed var(--line);
  cursor: pointer;

  &.no-border {
    border-top: none;
  }

  > svg:first-child {
    width: 20px;
    height: 20px;
    color: var(--ink-2);
    flex-shrink: 0;
  }

  .row-main {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .row-name {
    flex: 1;
    font-size: var(--fs-sub);
  }

  .row-sub {
    margin-top: 1px;
  }

  .row-tail {
    color: var(--ink-3);
  }

  .chev {
    width: 16px;
    height: 16px;
    color: var(--ink-3);
    flex-shrink: 0;
  }
}

/* ---------- 免责绿条 ---------- */
.me-note {
  margin-bottom: var(--sp-4);
}

.ver {
  text-align: center;
  padding-bottom: var(--sp-4);
}
</style>
