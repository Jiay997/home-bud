<!--
  MemberIosPage SC-21 iOS/额度变体
  无购买入口 + "当前设备暂不支持购买" + 额度用尽说明；保留会员权益说明。
-->
<template>
  <div class="page">
    <PageHeader title="会员 · 当前设备" />

    <!-- 设备不支持购买说明卡 -->
    <div class="card ios-card">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"
          stroke="var(--warn)"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
      <p class="ios-title">当前设备暂不支持购买</p>
      <p class="ios-body">
        受应用商店支付政策影响，本设备端暂未开放会员购买入口。
        你可以在其他支持的平台开通会员，同一账号权益通用。
      </p>
    </div>

    <!-- 额度用尽说明 -->
    <div class="card quota-card">
      <QuotaBar :used="user.quotaUsed" :limit="user.quotaLimit" :unlimited="user.quotaUnlimited" />
      <p class="quota-note">
        额度用尽后当日仍可浏览历史记录与报告，但无法发起新问答；
        次日 0 点自动重置为 {{ user.quotaLimit }} 次。
      </p>
    </div>

    <!-- 权益对照（只读展示） -->
    <div class="card compare">
      <div class="cmp-head">
        <span />
        <span class="cmp-col">免费</span>
        <span class="cmp-col pro">会员</span>
      </div>
      <div v-for="row in ROWS" :key="row.name" class="cmp-row">
        <span class="cmp-name">{{ row.name }}</span>
        <span class="cmp-val">{{ row.free }}</span>
        <span class="cmp-val pro">{{ row.pro }}</span>
      </div>
    </div>

    <p class="foot caption">如已在其他平台开通会员但未生效，请通过"反馈"联系我们</p>
  </div>
</template>

<script setup lang="ts">
import { useUserStore } from '@/stores/user'
import QuotaBar from '@/components/QuotaBar.vue'
import PageHeader from '@/components/PageHeader.vue'

const user = useUserStore()

/** 权益对照行 */
const ROWS = [
  { name: '每日问答次数', free: '5 次', pro: '不限次' },
  { name: '会员深度内容', free: '摘要', pro: '完整查看' },
  { name: '测评深入解读', free: '基础报告', pro: '策略建议' },
  { name: '历史重新生成', free: '不支持', pro: '支持' }
]
</script>

<style lang="scss" scoped>
.ios-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: var(--sp-2);
  margin-bottom: var(--sp-4);

  svg {
    width: 24px;
    height: 24px;
  }
}

.ios-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--warn);
}

.ios-body {
  font-size: var(--fs-sub);
  color: var(--ink-2);
  line-height: 1.7;
}

.quota-card {
  margin-bottom: var(--sp-4);
}

.quota-note {
  margin-top: var(--sp-3);
  font-size: var(--fs-caption);
  color: var(--ink-3);
  line-height: 1.6;
}

.compare {
  margin-bottom: var(--sp-4);
  padding: var(--sp-4) var(--sp-6);
}

.cmp-head,
.cmp-row {
  display: grid;
  grid-template-columns: 1.2fr 1fr 1fr;
  gap: var(--sp-2);
  align-items: center;
  padding: var(--sp-2) 0;
}

.cmp-head .cmp-col {
  text-align: center;
  font-weight: 600;
  font-size: var(--fs-sub);
  color: var(--ink-2);

  &.pro {
    color: var(--accent);
  }
}

.cmp-row {
  border-top: 1px dashed var(--line);

  .cmp-name {
    font-size: var(--fs-caption);
    color: var(--ink-2);
  }

  .cmp-val {
    text-align: center;
    font-size: var(--fs-caption);
    color: var(--ink-3);

    &.pro {
      color: var(--accent);
      font-weight: 600;
    }
  }
}

.foot {
  text-align: center;
}
</style>
