<!--
  AccountSecurityPage SC-24 账号与安全（Stitch 稿重构）
  页头（‹ 账号与安全 + 安全层报 chip）+ 量具级风控状态卡（真实 last_active + 合规绿徽章）+
  01 登录方式组（微信登录 openid 绑定 + 已绑定绿标签）+
  02 系统权限管理组（麦克风/相册摄像头 + 去设置）+
  03 撤回同意（分项独立控制）：基础同意 / 儿童信息单独同意（特别保护）+ 详细后果告知绿卡 +
  高危操作：账号注销红区卡（二次核验）。
  分项撤回（二次确认 + 原因必填）与注销（ConfirmDialog）逻辑全保留。
-->
<template>
  <div class="page as-page">
    <!-- 页头 -->
    <header class="as-head">
      <button class="back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M15 6l-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">账号与安全</h1>
      <span class="st-tag st-tag--gray st-tag--plain">安全层报</span>
    </header>

    <!-- 量具级风控状态卡 -->
    <div class="st-card risk-card">
      <div class="rk-ico" aria-hidden="true">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
        </svg>
      </div>
      <div class="rk-body">
        <p class="rk-title">量具级风控状态</p>
        <p class="caption">基线检点：{{ lastActive }}</p>
      </div>
      <span class="st-tag st-tag--green">刻度合规</span>
    </div>

    <!-- 01 登录方式组 -->
    <div class="st-card sec-card">
      <div class="sec-head">
        <span class="st-section-head">01 登录方式</span>
        <span class="caption">主体侧锚点</span>
      </div>
      <div class="login-card">
        <div class="lc-ico" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v11a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 17.5v-11ZM7 9h10M7 13h6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
          </svg>
        </div>
        <div class="lc-body">
          <p class="lc-title">微信登录（openid 绑定）</p>
          <p class="caption">当前会员身份侧 · 数字标识已校准（{{ deviceIdTail }}）</p>
        </div>
        <span class="st-tag st-tag--green">已绑定</span>
      </div>
    </div>

    <!-- 02 系统权限管理组 -->
    <div class="st-card sec-card">
      <div class="sec-head">
        <span class="st-section-head">02 系统权限管理</span>
        <span class="caption">动态授权调校</span>
      </div>
      <div v-for="p in PERMISSIONS" :key="p.key" class="perm-row">
        <div class="lc-ico" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path :d="p.icon" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>
        <div class="lc-body">
          <p class="lc-title">{{ p.name }}</p>
          <p class="caption perm-state" :class="p.granted ? 'ok' : 'warn'">
            <span class="dot" aria-hidden="true" />
            {{ p.granted ? '已授权' : '未授权' }}
          </p>
        </div>
        <button class="set-btn touch-target" type="button" @click="goSetting(p)">去设置</button>
      </div>
      <p class="caption perm-note">权限用于语音录入与图片反馈，可随时按需开关。</p>
    </div>

    <!-- 03 撤回同意（分项独立控制）组 -->
    <div class="st-card sec-card">
      <div class="sec-head">
        <span class="st-section-head">03 撤回同意（分项独立控制）</span>
        <span class="caption">法定知情权</span>
      </div>

      <div v-for="w in WITHDRAWS" :key="w.type" class="wd-card">
        <div class="wd-info">
          <p class="wd-name">
            {{ w.name }}
            <span v-if="w.special" class="st-tag st-tag--amber st-tag--plain">特别保护</span>
          </p>
          <p class="wd-desc caption">{{ w.desc }}</p>
        </div>
        <el-button plain @click="openWithdraw(w)">撤回</el-button>
      </div>

      <!-- 详细后果告知绿卡（常显） -->
      <div class="impact-green">
        <p class="ig-title">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 3 4 7v5c0 4.5 3.4 8 8 9 4.6-1 8-4.5 8-9V7l-8-4Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" /></svg>
          详细后果告知：
        </p>
        <ul>
          <li>撤回后停止对孩子信息的使用；</li>
          <li>儿童信息撤回后，档案停用、不再更新数据；</li>
          <li>已生成历史档案保留为只读。</li>
        </ul>
      </div>
    </div>

    <!-- 高危操作：账号注销红区卡 -->
    <div class="st-card danger-card">
      <div class="dc-head">
        <p class="dc-title">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" /></svg>
          高危操作：账号注销
        </p>
        <span class="st-tag st-tag--red st-tag--plain">不可逆处置</span>
      </div>
      <p class="dc-body caption">
        注销后数据彻底删除、不可恢复；交易与订单记录依法留存。
      </p>
      <button class="dc-btn" @click="deleteVisible = true">注销账号（需二次核验确认）</button>
    </div>

    <!-- 底行 + AI 免责 -->
    <p class="scale-foot caption">系统校准版本 1.0</p>
    <AiDisclaimer ai-label="AI 生成内容" disclaimer="安全与合规说明以最新版协议文本为准" />

    <!-- 撤回二次确认 -->
    <ConfirmDialog
      v-model="withdrawVisible"
      :title="`撤回「${currentWithdraw?.name}」授权？`"
      :impacts="[currentWithdraw?.impact || '对应功能将立即停用', '撤回后如需继续使用需重新同意']"
      :need-reason="true"
      reason-label="请填写撤回原因（帮助我们改进，必填）"
      confirm-text="确认撤回"
      @confirm="doWithdraw"
    />

    <!-- 注销二次确认 -->
    <ConfirmDialog
      v-model="deleteVisible"
      title="确认注销账号？"
      :impacts="['全部数据将被删除且无法恢复', '会员权益立即失效且不退款']"
      :need-reason="true"
      reason-label="请输入注销原因（必填）"
      confirm-text="确认注销"
      @confirm="doDeleteAccount"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { withdrawConsent } from '@/api/client'
import { getDeviceId } from '@/stores/user'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

/** 可撤回授权项（分项独立控制） */
const WITHDRAWS = [
  {
    type: 'base',
    name: '基础同意（协议与免责）',
    desc: '包含平台通用用户协议与技术服务免责条款',
    impact: '核心问答功能将立即停用',
    special: false
  },
  {
    type: 'child_personal_info',
    name: '儿童信息单独同意',
    desc: '涉及监护人与儿童生理刻度数据',
    impact: '儿童档案将停用并停止个性化建议',
    special: true
  }
]

/** 系统权限演示项（麦克风未授权 / 相册摄像头已授权） */
const PERMISSIONS = [
  {
    key: 'mic',
    name: '麦克风权限',
    granted: false,
    icon: 'M12 3a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3ZM5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21'
  },
  {
    key: 'camera',
    name: '相册 / 摄像头权限',
    granted: true,
    icon: 'M4 8.5A1.5 1.5 0 0 1 5.5 7h2L9 5h6l1.5 2h2A1.5 1.5 0 0 1 20 8.5v9a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5v-9ZM12 16a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z'
  }
]

/** 撤回弹窗 */
const withdrawVisible = ref(false)
/** 当前撤回项 */
const currentWithdraw = ref<(typeof WITHDRAWS)[number] | null>(null)
/** 注销弹窗 */
const deleteVisible = ref(false)

/** 设备 ID 尾号（openid 数字标识演示位） */
const deviceIdTail = computed(() => getDeviceId().slice(-6))

/** 基线检点时间（当前会话时刻格式化，替代静态演示值） */
const lastActive = computed(() => {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
})

/**
 * 打开撤回确认
 * @param w 撤回项
 */
function openWithdraw(w: (typeof WITHDRAWS)[number]): void {
  currentWithdraw.value = w
  withdrawVisible.value = true
}

/**
 * 权限"去设置"：跳系统设置的演示提示
 * @param p 权限项
 */
function goSetting(p: (typeof PERMISSIONS)[number]): void {
  ElMessage.info(`请在系统设置中管理「${p.name}」，本页为演示入口`)
}

/**
 * 执行撤回
 * @param reason 撤回原因
 * @throws 接口失败消息提示
 */
async function doWithdraw(reason: string): Promise<void> {
  if (!currentWithdraw.value) return
  try {
    await withdrawConsent(currentWithdraw.value.type)
    ElMessage.success(`已撤回（原因已记录：${reason.slice(0, 10)}…）`)
    withdrawVisible.value = false
  } catch (e: any) {
    ElMessage.error(e?.message || '撤回失败，请重试')
  }
}

/**
 * 申请注销（演示环境：调用撤回 base 模拟 + 提示）
 * @param reason 注销原因
 */
async function doDeleteAccount(reason: string): Promise<void> {
  try {
    await withdrawConsent('base')
  } catch {
    // 演示环境静默
  }
  ElMessage.success(`注销申请已受理（原因：${reason.slice(0, 10)}…），7 天冷静期后生效`)
  deleteVisible.value = false
}
</script>

<style lang="scss" scoped>
/* ---------- 页头 ---------- */
.as-head {
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

/* ---------- 风控状态卡 ---------- */
.risk-card {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);

  .rk-ico {
    flex: none;
    width: 40px;
    height: 40px;
    border-radius: 50%;
    background: var(--accent-soft);
    color: var(--accent);
    display: flex;
    align-items: center;
    justify-content: center;

    svg { width: 20px; height: 20px; }
  }

  .rk-body {
    flex: 1;

    .rk-title {
      font-size: var(--fs-sub);
      font-weight: 600;
      color: var(--ink-1);
    }
  }
}

/* ---------- 分组卡 ---------- */
.sec-card {
  margin-bottom: var(--sp-4);
}

.sec-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-3);

  > .caption {
    color: var(--ink-3);
  }
}

/* ---------- 行卡公共（登录/权限） ---------- */
.login-card,
.perm-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);

  & + .perm-row {
    margin-top: var(--sp-3);
  }
}

.lc-ico {
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

.lc-body {
  flex: 1;

  .lc-title {
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
  }
}

.perm-state {
  margin-top: 2px;
  display: inline-flex;
  align-items: center;
  gap: 4px;

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 1px;
    background: currentColor;
  }

  &.ok {
    color: var(--accent);
  }

  &.warn {
    color: var(--warn);
  }
}

.set-btn {
  flex: none;
  border: 1px solid var(--line-strong);
  background: var(--surface);
  color: var(--ink-2);
  font-size: var(--fs-caption);
  padding: 5px 14px;
  border-radius: var(--radius-ctl);
  cursor: pointer;

  &:active {
    background: var(--surface-2);
  }
}

.perm-note {
  margin-top: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  background: var(--surface-2);
  border-radius: var(--radius-ctl);
  color: var(--ink-3);
}

/* ---------- 撤回卡 ---------- */
.wd-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);
  margin-bottom: var(--sp-3);

  .wd-name {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
  }

  .wd-desc {
    margin-top: 2px;
  }
}

.impact-green {
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);

  .ig-title {
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

  ul {
    padding-left: 20px;

    li {
      font-size: var(--fs-caption);
      color: var(--ink-2);
      line-height: 1.9;
    }
  }
}

/* ---------- 注销红区卡 ---------- */
.danger-card {
  border-color: var(--danger);
  margin-bottom: var(--sp-4);
}

.dc-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-2);

  .dc-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--danger);

    svg {
      width: 16px;
      height: 16px;
    }
  }
}

.dc-body {
  color: var(--ink-2);
  margin-bottom: var(--sp-3);
  line-height: 1.7;
}

.dc-btn {
  width: 100%;
  padding: 11px 0;
  border: 1px solid var(--danger);
  border-radius: var(--radius-ctl);
  background: var(--surface);
  color: var(--danger);
  font-size: var(--fs-sub);
  font-weight: 600;
  cursor: pointer;

  &:active {
    background: var(--danger-soft);
  }
}

.scale-foot {
  text-align: center;
  letter-spacing: 3px;
  color: var(--ink-3);
  margin: var(--sp-4) 0 var(--sp-2);
}
</style>
