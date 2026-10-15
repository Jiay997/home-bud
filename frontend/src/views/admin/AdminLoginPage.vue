<!--
  文件级注释：PA-01 后台登录与 MFA 页面（Stitch mfa 稿形态）
  流程：账号密码登录（POST /admin/login）→ mfa_required 时进入验证码步骤
       （POST /admin/mfa/verify，开发模式验证码 123456，60s 倒计时提示）
       → 校验通过后写入 localStorage('jiaban_admin_token' / 'jiaban_admin_info') → 跳转 /admin/dashboard
  布局：顶部安全装饰条 + 居中白卡（max-width 420）+ 底部合规条；背景带量具刻度网格装饰。
  异常：连续失败 5 次提示锁定（浅黄警示条）；最近登录无记录时展示"首次登录"占位。
-->
<template>
  <div class="pa-login">
    <!-- 顶部安全装饰条 -->
    <header class="sec-header">
      <div class="sec-left">
        <span class="brand-mark">
          <svg class="shield-svg" viewBox="0 0 24 24" aria-hidden="true">
            <path d="M12 2L4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3z" fill="currentColor" />
            <path
              d="M8.6 12l2.4 2.4 4.6-4.6"
              fill="none"
              stroke="#fff"
              stroke-width="2"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
        </span>
        <span class="brand-title">小光景后台管理中心</span>
      </div>
      <div class="sec-right">
        <span class="pulse-dot"></span>
        <span>管理端登录需完成二次验证</span>
        <span class="sep">|</span>
        <span>操作全程写入审计留痕</span>
      </div>
    </header>

    <!-- 中央登录区 -->
    <main class="sec-main">
      <!-- 登录白卡 -->
      <div class="login-card">
        <div class="card-head">
          <div class="shield-box">
            <svg class="shield-svg" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 2L4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3z" fill="currentColor" />
              <path
                d="M8.6 12l2.4 2.4 4.6-4.6"
                fill="none"
                stroke="#fff"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              />
            </svg>
          </div>
          <h1 class="card-title">管理员登录</h1>
          <p class="card-sub">小光景后台系统 · 最小权限访问控制</p>
        </div>

        <!-- 终端准入安全刻度行（静态展示） -->
        <div class="scale-row">
          <span class="scale-label">
            <el-icon :size="16"><Odometer /></el-icon>
            <span>登录安全检查项</span>
          </span>
          <span class="scale-badge">账号密码 + 二次验证</span>
        </div>

        <el-form class="login-form" @submit.prevent>
          <!-- 账号 -->
          <div class="field">
            <label class="field-label">账号</label>
            <el-input
              v-model="form.username"
              size="large"
              placeholder="请输入管理员工作账号"
              :prefix-icon="User"
              :disabled="loading"
              clearable
            />
          </div>

          <!-- 密码（可切换明文） -->
          <div class="field">
            <label class="field-label">密码</label>
            <el-input
              v-model="form.password"
              size="large"
              type="password"
              show-password
              placeholder="请输入密码"
              :prefix-icon="Lock"
              :disabled="loading"
              @keyup.enter="step === 1 ? handleLogin() : handleVerify()"
            />
          </div>

          <!-- 二次验证 (MFA) -->
          <div class="mfa-block">
            <div class="mfa-head">
              <span class="mfa-title">
                <el-icon :size="16"><Key /></el-icon>
                <span>二次验证 (MFA)</span>
              </span>
              <span class="mfa-caption">动态身份验证码</span>
            </div>
            <div class="mfa-row">
              <el-input
                v-model="form.code"
                ref="codeInputRef"
                size="large"
                class="mfa-input"
                maxlength="6"
                placeholder="6 位数字验证码"
                :disabled="loading"
                @keyup.enter="step === 1 ? handleGetCode() : handleVerify()"
              />
              <el-button
                size="large"
                class="code-btn"
                :disabled="loading || (step === 2 && countdown > 0)"
                @click="handleGetCode"
              >
                {{ step === 2 && countdown > 0 ? `${countdown}s 后重发` : '获取验证码' }}
              </el-button>
            </div>
            <p class="mfa-tip">验证码 5 分钟内有效，60 秒后可重发</p>
            <el-button v-if="step === 2" link type="primary" class="back-link" @click="backToStep1">
              返回重新输入账号
            </el-button>
          </div>

          <!-- 记住此设备 -->
          <el-checkbox v-model="rememberDevice" class="remember">记住此设备（7 天）</el-checkbox>

          <!-- 登录主按钮 -->
          <el-button
            type="primary"
            class="submit-btn"
            size="large"
            native-type="submit"
            :loading="loading"
            @click="step === 1 ? handleLogin() : handleVerify()"
          >
            {{ step === 1 ? '登 录' : '验证并登录' }}
          </el-button>
        </el-form>

        <!-- 底部信息区 -->
        <div class="card-foot">
          <div class="foot-line">
            <el-icon :size="14"><Avatar /></el-icon>
            <span>角色说明（最小权限）：超级管理员 / 内容运营 / 客服 / 专家</span>
          </div>
          <div class="foot-line">
            <el-icon :size="14"><Clock /></el-icon>
            <span>最近登录：{{ lastLoginText }}</span>
          </div>
          <!-- 连续失败 5 次锁定警示条（浅黄底） -->
          <div v-if="lockHint" class="lock-warn">
            <el-icon :size="16"><Warning /></el-icon>
            <span>{{ lockHint }}</span>
          </div>
        </div>
      </div>
    </main>

    <!-- 底部合规条 -->
    <footer class="sec-footer">
      <div class="foot-left">
        <el-icon :size="14"><CircleCheck /></el-icon>
        <span>小光景后台安全中心 · 管理操作写入不可篡改的审计记录</span>
      </div>
      <div class="foot-right">
        <span>最小权限访问</span>
        <span class="sep">·</span>
        <span>高风险操作二次确认并留原因</span>
      </div>
    </footer>
  </div>
</template>

<script setup lang="ts">
/**
 * 文件级注释：见模板顶部。登录两步流程 + 失败计数锁定提示 + 登录态写入 + 记住设备勾选（预留）。
 */
import { nextTick, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import type { InputInstance } from 'element-plus'
import { Avatar, CircleCheck, Clock, Key, Lock, Odometer, User, Warning } from '@element-plus/icons-vue'
import { adminApi, setToken, setAdminInfo, ApiError } from '../../api/admin'

const router = useRouter()

/** 验证码输入框实例（SIM-24：进入 MFA 步骤后 nextTick 聚焦，防御时序/焦点失效） */
const codeInputRef = ref<InputInstance>()

/** 当前步骤：1=账号密码，2=MFA 验证码 */
const step = ref(1)
/** 登录表单数据 */
const form = reactive({ username: '', password: '', code: '' })
/** 第一步返回的 MFA 票据 */
const mfaTicket = ref('')
/** 提交中标志（防止重复提交） */
const loading = ref(false)
/** 连续失败计数（达到 5 次提示锁定） */
const failCount = ref(0)
/** 锁定/错误提示文案 */
const lockHint = ref('')
/** 验证码重发倒计时（秒） */
const countdown = ref(0)
/** 倒计时定时器句柄 */
let timer: ReturnType<typeof setInterval> | null = null
/** 最近登录占位文案（无记录显示"首次登录"） */
const lastLoginText = ref('首次登录')
/** 记住此设备（7 天）勾选（接口暂不支持，UI 状态预留） */
const rememberDevice = ref(false)

/**
 * 函数级注释：启动验证码 60s 倒计时
 */
function startCountdown(): void {
  countdown.value = 60
  stopCountdown()
  timer = setInterval(() => {
    countdown.value--
    if (countdown.value <= 0) stopCountdown()
  }, 1000)
}

/**
 * 函数级注释：停止倒计时定时器
 */
function stopCountdown(): void {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

/**
 * 函数级注释：返回第一步重新输入账号密码
 */
function backToStep1(): void {
  step.value = 1
  form.code = ''
  stopCountdown()
}

/**
 * 函数级注释：获取验证码
 * 第一步时先执行账号密码登录（成功且需 MFA 时自动进入第二步并启动倒计时）；
 * 第二步时重置倒计时（开发模式验证码固定，重发仅刷新时限提示）。
 */
async function handleGetCode(): Promise<void> {
  if (step.value === 2 && countdown.value > 0) return
  if (step.value === 1) {
    await handleLogin()
  } else {
    startCountdown()
    ElMessage.success('验证码已重发')
  }
}

/**
 * 函数级注释：进入 MFA 步骤的统一入口处理（SIM-24）
 * 1. 提示「验证码已自动发送」（区别于按钮「Xs 后可重发」的重发语义）；
 * 2. nextTick 后聚焦验证码输入框：账号密码成功到进入第二步存在一次视图切换，
 *    不做防御聚焦时偶发首次输入无效（焦点仍停留在已禁用的密码框）。
 */
async function enterMfaStep(): Promise<void> {
  step.value = 2
  startCountdown()
  ElMessage.success('验证码已自动发送，请输入收到的 6 位验证码')
  await nextTick()
  codeInputRef.value?.focus()
}

/**
 * 函数级注释：第一步登录（账号密码）
 * @throws 无异常抛出；失败时计数并展示错误提示
 */
async function handleLogin(): Promise<void> {
  if (!form.username.trim() || !form.password) {
    ElMessage.warning('请输入账号与密码')
    return
  }
  loading.value = true
  try {
    const data: any = await adminApi.login(form.username.trim(), form.password)
    failCount.value = 0
    lockHint.value = ''
    if (data?.mfa_required) {
      // 需要二次验证：保存票据进入第二步（SIM-24：自动发码提示 + 聚焦防御）
      mfaTicket.value = data.mfa_ticket || ''
      await enterMfaStep()
    } else if (data?.token) {
      // 免 MFA 场景（如记住设备），直接完成登录
      doLoginSuccess(data)
    } else {
      ElMessage.error('登录响应缺少凭据，请联系管理员')
    }
  } catch (e) {
    handleLoginError(e)
  } finally {
    loading.value = false
  }
}

/**
 * 函数级注释：第二步 MFA 验证码校验
 */
async function handleVerify(): Promise<void> {
  if (!form.code.trim()) {
    ElMessage.warning('请输入验证码')
    return
  }
  loading.value = true
  try {
    const data: any = await adminApi.mfaVerify(mfaTicket.value, form.code.trim())
    failCount.value = 0
    doLoginSuccess(data)
  } catch (e) {
    handleLoginError(e)
  } finally {
    loading.value = false
  }
}

/**
 * 函数级注释：登录成功后写入本地登录态并跳转后台首页
 * @param data MFA 校验/登录接口返回的 {token, role, display_name, domain_scope, menus}
 */
function doLoginSuccess(data: any): void {
  setToken(data.token)
  setAdminInfo({
    role: data.role,
    display_name: data.display_name,
    domain_scope: data.domain_scope,
    menus: data.menus || [],
  })
  stopCountdown()
  ElMessage.success(`欢迎，${data.display_name || '管理员'}`)
  router.push('/admin/dashboard')
}

/**
 * 函数级注释：统一处理登录失败（计数 + 锁定提示）
 * @param e 捕获到的异常（ApiError 或其他）
 */
function handleLoginError(e: any): void {
  failCount.value++
  const msg = e instanceof ApiError ? e.message : '登录失败，请稍后重试'
  // 连续失败 5 次提示锁定（与原型"连续失败 5 次锁定 15 分钟"一致）
  lockHint.value =
    failCount.value >= 5
      ? `连续失败 ${failCount.value} 次：账号已锁定 15 分钟，请稍后再试`
      : msg
  ElMessage.error(msg)
}

onUnmounted(stopCountdown)
</script>

<style scoped>
/* 页面骨架：顶部安全条 + 弹性中央区 + 底部合规条 */
.pa-login {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: var(--bg);
}

/* ---------- 顶部安全装饰条 ---------- */
.sec-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 32px;
  background: var(--surface);
  border-bottom: 1px solid var(--line);
}

.sec-left {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

/* 盾徽圆角图标 */
.brand-mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  background: var(--accent);
  color: var(--accent);
  box-shadow: var(--shadow-e1);
}

.shield-svg {
  width: 18px;
  height: 18px;
}

.brand-title {
  font-size: var(--fs-title);
  font-weight: 600;
  color: var(--ink-1);
  white-space: nowrap;
}

.sec-right {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--ink-3);
  font-size: var(--fs-caption);
  white-space: nowrap;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
  animation: jiaban-pulse 2s ease-in-out infinite;
}

@keyframes jiaban-pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

.sep {
  color: var(--line-strong);
}

/* ---------- 中央登录区 ---------- */
.sec-main {
  position: relative;
  display: flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  padding: 24px 16px;
  overflow: hidden;
}

/* 背景刻度装饰：左右两侧 5px 小刻度，取自签名组件的标尺层；不用卡片框、不用假编号 */
.bg-ruler {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.bg-ruler::before,
.bg-ruler::after {
  content: '';
  position: absolute;
  top: 8%;
  bottom: 8%;
  width: 5px;
  background-image: repeating-linear-gradient(
    to bottom,
    var(--line-strong) 0 1px,
    transparent 1px 8px
  );
  opacity: 0.5;
}

.bg-ruler::before {
  left: 24px;
}

.bg-ruler::after {
  right: 24px;
}

/* 登录白卡 */
.login-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 420px;
  padding: 32px;
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  box-shadow: 0 4px 24px -4px rgba(15, 30, 28, 0.05);
}

.card-head {
  margin-bottom: 20px;
  text-align: center;
}

.shield-box {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  margin-bottom: 8px;
  border-radius: 12px;
  background: var(--accent-soft);
  color: var(--accent);
}

.shield-box .shield-svg {
  width: 26px;
  height: 26px;
}

.card-title {
  font-size: var(--fs-display);
  font-weight: 600;
  color: var(--ink-1);
  line-height: 1.3;
}

.card-sub {
  margin-top: 4px;
  font-size: var(--fs-sub);
  color: var(--ink-3);
}

/* 终端准入安全刻度行（静态展示） */
.scale-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px;
  margin-bottom: 20px;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  background: var(--surface-2);
  font-size: var(--fs-caption);
}

.scale-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--ink-2);
}

.scale-badge {
  padding: 2px 6px;
  border: 1px solid var(--accent-line);
  border-radius: 4px;
  background: var(--surface);
  color: var(--accent);
  font-family: var(--font-numeric);
  font-weight: 500;
  white-space: nowrap;
}

/* ---------- 表单 ---------- */
.field + .field {
  margin-top: 16px;
}

.field-label {
  display: block;
  margin-bottom: 6px;
  font-size: var(--fs-sub);
  font-weight: 500;
  color: var(--ink-1);
}

/* MFA 区块 */
.mfa-block {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid var(--line);
}

.mfa-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
}

.mfa-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-sub);
  font-weight: 500;
  color: var(--ink-1);
}

.mfa-title .el-icon {
  color: var(--accent);
}

.mfa-caption {
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.mfa-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mfa-input {
  flex: 1;
}

.mfa-input :deep(.el-input__inner) {
  text-align: center;
  letter-spacing: 3px;
  font-family: var(--font-numeric);
}

/* 获取验证码：墨青描边幽灵按钮 */
.code-btn {
  flex: none;
  border-color: var(--accent);
  background: transparent;
}

.code-btn:hover:not(.is-disabled) {
  border-color: var(--accent-press);
  background: var(--accent-soft);
  color: var(--accent-press);
}

.mfa-tip {
  margin-top: 6px;
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.back-link {
  margin-top: 4px;
  font-size: var(--fs-caption);
}

.remember {
  margin: 14px 0 16px;
}

/* 登录主按钮 */
.submit-btn {
  width: 100%;
  font-weight: 700;
  letter-spacing: 6px;
}

/* ---------- 卡片底部信息区 ---------- */
.card-foot {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--line);
  font-size: var(--fs-caption);
  color: var(--ink-2);
}

.foot-line {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  line-height: 1.6;
}

.foot-line .el-icon {
  flex: none;
  margin-top: 3px;
  color: var(--ink-3);
}

/* 连续失败锁定警示条（浅黄底） */
.lock-warn {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  padding: 10px;
  border: 1px solid var(--warn);
  border-radius: var(--radius-ctl);
  background: var(--warn-soft);
  color: var(--warn);
  font-size: var(--fs-caption);
  font-weight: 500;
}

/* ---------- 底部合规条 ---------- */
.sec-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 32px;
  background: var(--surface);
  border-top: 1px solid var(--line);
  font-size: var(--fs-caption);
  color: var(--ink-3);
}

.foot-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

.foot-left .el-icon {
  color: var(--accent);
}

.foot-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
