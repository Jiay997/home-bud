<!--
  StartPage SC-01 启动免责与协议同意页（Stitch 稿重构）
  版式：合规版本徽章 + 品牌主标副标 →「一句能带走的话 + 示例问题预告」→
  「免责与使用说明」卡（服务定位标尺条外露；绿底免责强调块 / 服务性质界定三条 /
  四协议文字链折进 details 展开区，合规文本一字不删）→ AiDisclaimer 常驻条 →
  同意勾选 + 进入按钮（未勾选置灰；「进入」落在首屏 812px 内）。
  逻辑：同意后 POST /consent/agree(base)，首次标记与 token 存 localStorage，同意记录本地存证。
-->
<template>
  <div class="start-page">
    <!-- 登录过期提示（全局 1101 处理跳转而来；非用户主动登出） -->
    <div v-if="sessionExpired" class="session-note" role="status">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.75" />
        <path d="M12 7.5V12l3 2" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
      <span>登录已过期，请重新进入</span>
    </div>

    <div class="start-layout">
      <section class="start-intro" aria-labelledby="start-title">
        <header class="brand-lockup">
          <div class="brand-mark" aria-hidden="true">
            <span class="mark-rail"></span>
            <span class="mark-tick mark-tick--one"></span>
            <span class="mark-tick mark-tick--two"></span>
            <span class="mark-tick mark-tick--three"></span>
            <span class="mark-cursor"></span>
          </div>
          <div class="brand-copy">
            <h1 id="start-title" class="brand">小光景</h1>
            <p class="slogan">一家人的养育参考</p>
          </div>
        </header>

        <div class="intro-rule" aria-hidden="true">
          <span></span><span></span><span></span><span></span><span></span>
        </div>

        <div class="takeaway">
          <p class="tk-line">具体的难题，<span>值得</span>具体的回答。</p>
          <p class="tk-lead">从一个正在发生的生活片段开始。</p>
        </div>

        <section class="question-index" aria-label="示例问题">
          <h2>可以这样问</h2>
          <ul class="tk-examples">
            <li v-for="q in PREVIEW_QUESTIONS" :key="q">
              <span class="question-mark" aria-hidden="true"></span>
              <span>{{ q }}</span>
            </li>
          </ul>
        </section>

        <p class="intro-footnote">育儿观察 · 宠物相处 · 家庭协作</p>
      </section>

      <section class="legal-card" aria-labelledby="legal-title">
      <!-- 卡头：标题 + 强制知悉标注 -->
      <div class="legal-head">
        <div>
          <h2 id="legal-title" class="legal-title">免责与使用说明</h2>
          <p class="legal-subtitle">请先了解服务边界，再开始使用</p>
        </div>
        <span class="sec-badge">合规版本 V2.4</span>
      </div>

      <!-- 服务定位标尺行（关键定位常驻外露） -->
      <div class="position-strip">
        <span class="strip-left">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path
              d="M12 3 5 5.5v6c0 4.5 3 7.9 7 9.5 4-1.6 7-5 7-9.5v-6L12 3Z"
              stroke="currentColor"
              stroke-width="1.75"
              stroke-linejoin="round"
            />
            <path d="m9 11.5 2.2 2.2L15.5 9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          服务定位标尺
        </span>
        <strong class="strip-right">非医疗 · 科普决策参考</strong>
      </div>

      <!-- 法务正文折进展开区：合规文本一字不删，默认收起让「进入」落在首屏 -->
      <details class="legal-details">
        <summary>
          <span>完整条款与协议全文</span>
          <svg class="sum-chev" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="m8 10 4 4 4-4" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </summary>
        <div class="legal-body">
          <!-- 绿底免责强调块 -->
          <div class="emphasis-block">
            本产品为养育科普参考工具，不替代医生、心理咨询师、教师、执业兽医。紧急情况请立即联系线下专业机构。
          </div>

          <!-- 服务性质界定条款 -->
          <ol class="terms">
            <li>
              <strong>服务性质界定：</strong>“小光景”依托专业多模型多智能体架构提供育儿、儿童行为观察及家庭协作建议。所有分析结论、测评量表分值与应对方案仅供监护人参考，严禁作为临床诊断或处方依据。
            </li>
            <li>
              <strong>紧急危机警示：</strong>若儿童出现高热惊厥、呼吸困难、急性外伤、持续自伤情绪或意识障碍等危急情况，系统不具备急救指引效力，请立即拨打120或前往实体三甲医院急诊就医。
            </li>
            <li>
              <strong>未成年人隐私专章：</strong>我们执行《儿童个人信息网络保护规定》，采集的成长记录均进行端到端加密与敏感信息隔离存储，监护人享有完全的撤回授权与数据清除权利。
            </li>
          </ol>

          <!-- 协议文字链 -->
          <p class="agreement-lead">请仔细通读以下法规协议条款：</p>
          <div class="agreements">
            <span class="agreement-link">《用户协议》</span>
            <i class="link-sep" aria-hidden="true">|</i>
            <span class="agreement-link">《隐私政策》</span>
            <i class="link-sep" aria-hidden="true">|</i>
            <span class="agreement-link">《免责声明》</span>
            <i class="link-sep" aria-hidden="true">|</i>
            <span class="agreement-link">《儿童个人信息处理规则》（易懂版）</span>
          </div>
        </div>
      </details>

      <!-- AI 生成标识常驻条（合规要求：与其他页面页脚标识一致，文案口径同 AiDisclaimer 既有用法） -->
      <AiDisclaimer ai-label="AI 生成内容" disclaimer="仅供参考，不替代医生诊断" />

      <!-- 同意勾选 -->
      <label class="agree-row">
        <input
          v-model="agreed"
          type="checkbox"
          class="agree-box"
          :aria-describedby="!agreed ? 'consent-hint' : undefined"
        />
        <span>我已阅读并同意上述全部协议</span>
      </label>
      <p v-if="!agreed" id="consent-hint" class="consent-hint">勾选后即可继续进入小光景</p>

      <!-- 进入按钮（未勾选置灰不可点） -->
      <el-button
        type="primary"
        size="large"
        class="enter-btn"
        :disabled="!agreed || entering"
        :loading="entering"
        @click="enter"
      >
        进入
      </el-button>
      <p v-if="enterError" class="enter-error" role="alert">{{ enterError }}</p>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { agreeConsent } from '@/api/client'
import { useUserStore, getDeviceId } from '@/stores/user'
import AiDisclaimer from '@/components/AiDisclaimer.vue'

/** 首次进入标记键名 */
const FIRST_FLAG = 'jiaban_first_entered'
/** 同意记录本地存证键名（类型/版本/时间/设备） */
const CONSENT_RECORD_KEY = 'jiaban_consent_record'
/** 协议版本号（随 V2.4 徽章） */
const CONSENT_VERSION = 'V2.4'

/** 示例问题预告（与首页 chips 同语汇，进不来也先看到产品在答什么） */
const PREVIEW_QUESTIONS = ['孩子夜里频繁醒、接觉难', '入托分离焦虑怎么办', '猫哈气不让抱']

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

/** 是否勾选同意 */
const agreed = ref(!!localStorage.getItem(FIRST_FLAG))
/** 进入中 */
const entering = ref(false)
/** 进入失败信息 */
const enterError = ref('')

/** 会话过期提示（由全局 1101 处理带 ?session=expired 跳转而来） */
const sessionExpired = computed(() => route.query.session === 'expired')

/**
 * 写入本地同意记录存证（类型/版本/时间/设备前 8 位），仅供合规取证，不在页面展示
 */
function saveRecord(): void {
  const record = {
    type: 'base',
    version: CONSENT_VERSION,
    time: new Date().toLocaleString('zh-CN', { hour12: false }),
    device: getDeviceId().slice(0, 8)
  }
  localStorage.setItem(CONSENT_RECORD_KEY, JSON.stringify(record))
}

/**
 * 进入应用：设备登录 → 提交 base 同意 → 标记首次与存证 → 跳转首页
 * @throws 登录或同意接口失败时内联展示错误
 */
async function enter(): Promise<void> {
  entering.value = true
  enterError.value = ''
  try {
    await userStore.login()
  } catch (e: any) {
    enterError.value = e?.message || '登录失败，请检查网络后重试'
    entering.value = false
    return
  }
  try {
    await agreeConsent('base')
  } catch (e: any) {
    if (e?.code === 1101) {
      // 本地残留 token 已失效（access token 2h 过期/换库）：清凭证 → 重新设备登录 → 重试一次
      userStore.logout()
      try {
        await userStore.login()
        await agreeConsent('base')
      } catch (retryErr: any) {
        if (!String(retryErr?.message || '').includes('已同意')) {
          enterError.value = '协议提交失败：' + (retryErr?.message || '请重试')
          entering.value = false
          return
        }
      }
    } else if (e?.code !== 0 && !String(e?.message || '').includes('已同意')) {
      // 已同意（重复提交）不阻断进入
      enterError.value = '协议提交失败：' + (e?.message || '请重试')
      entering.value = false
      return
    }
  }
  localStorage.setItem(FIRST_FLAG, '1')
  saveRecord()
  void getDeviceId // device id 已由 login 内部生成并持久化
  userStore.refreshQuota()
  const redirect = (route.query.redirect as string) || '/app/home'
  router.replace(redirect)
}
</script>

<style lang="scss" scoped>
.start-page {
  width: 100%;
  min-height: 100dvh;
  padding: clamp(28px, 5vh, 56px) 28px 40px;
  border-bottom: 1px solid var(--line);
  background: var(--bg);
}

.start-layout {
  width: min(1120px, 100%);
  min-height: calc(100dvh - 96px);
  margin: 0 auto;
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(400px, 0.88fr);
  align-items: center;
  gap: clamp(48px, 8vw, 116px);
}

.session-note {
  position: relative;
  z-index: 1;
  width: min(1120px, 100%);
  margin: 0 auto 16px;
  padding: 10px 14px;
  display: flex;
  align-items: center;
  gap: 8px;
  border-radius: var(--radius-ctl);
  background: var(--warn-soft);
  color: var(--warn);
  font-size: var(--fs-sub);

  svg { width: 18px; height: 18px; flex: none; }
}

.start-intro { min-width: 0; padding: 12px 0 20px; }

.brand-lockup {
  display: flex;
  align-items: center;
  gap: 18px;
}

.brand-mark {
  position: relative;
  width: 54px;
  height: 54px;
  flex: none;
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-face);
  background: var(--accent-soft);
}

.mark-rail {
  position: absolute;
  left: 26px;
  top: 10px;
  bottom: 10px;
  width: 1px;
  background: var(--accent);
}

.mark-tick {
  position: absolute;
  left: 20px;
  width: 7px;
  height: 1px;
  background: var(--accent);
}

.mark-tick--one { top: 16px; }
.mark-tick--two { top: 26px; width: 12px; }
.mark-tick--three { top: 36px; }

.mark-cursor {
  position: absolute;
  top: 22px;
  left: 22px;
  width: 9px;
  height: 9px;
  border: 2px solid var(--surface);
  border-radius: 2px;
  background: var(--accent);
}

.brand {
  color: var(--ink-1);
  font-size: 32px;
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: 0.08em;
}

.slogan { margin-top: 7px; color: var(--ink-3); font-size: var(--fs-sub); }

.intro-rule {
  display: flex;
  gap: 0;
  width: min(430px, 88%);
  height: 14px;
  margin: 40px 0 28px;
  border-top: 1px solid var(--line-strong);
  background: repeating-linear-gradient(90deg, var(--line-strong) 0 1px, transparent 1px 8px);
  background-size: 100% 6px;
  background-repeat: no-repeat;

  span { width: 20%; height: 8px; border-right: 1px solid var(--line-strong); }
  span:nth-child(2), span:nth-child(4) { height: 5px; }
  span:nth-child(3) { height: 12px; border-color: var(--accent); }
}

.takeaway { max-width: 560px; }

.tk-line {
  color: var(--ink-1);
  font-size: 38px;
  font-weight: 600;
  line-height: 1.38;
  text-wrap: balance;
}

.tk-line span { white-space: nowrap; }

.tk-lead { margin-top: 12px; color: var(--ink-3); font-size: var(--fs-body); }

.question-index { margin-top: 38px; }

.question-index h2 {
  margin-bottom: 8px;
  color: var(--ink-2);
  font-size: var(--fs-caption);
  font-weight: 500;
}

.tk-examples {
  list-style: none;
  border-top: 1px solid var(--line);
}

.tk-examples li {
  min-height: 48px;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 1px solid var(--line);
  color: var(--ink-2);
  font-size: var(--fs-sub);
}

.question-mark {
  width: 6px;
  height: 6px;
  flex: none;
  border-radius: 1px;
  background: var(--accent);
}

.intro-footnote {
  margin-top: 28px;
  color: var(--ink-3);
  font-size: var(--fs-caption);
}

.legal-card {
  min-width: 0;
  padding: clamp(22px, 3vw, 34px);
  border: 1px solid var(--line);
  border-radius: var(--radius-face);
  background: var(--surface);
}

.legal-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 22px;
}

.legal-title { color: var(--ink-1); font-size: 21px; font-weight: 600; line-height: 1.35; }
.legal-subtitle { margin-top: 6px; color: var(--ink-3); font-size: var(--fs-caption); }

.sec-badge {
  flex: none;
  padding: 3px 8px;
  border: 1px solid var(--line);
  border-radius: 4px;
  color: var(--ink-3);
  font-family: var(--font-numeric);
  font-size: 10px;
  white-space: nowrap;
}

.position-strip {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
  padding: 12px 14px;
  border-radius: var(--radius-ctl);
  background: var(--accent-soft);
}

.strip-left { display: flex; align-items: center; gap: 8px; color: var(--ink-2); font-size: var(--fs-sub); }
.strip-left svg { width: 17px; height: 17px; flex: none; color: var(--accent); }
.strip-right { color: var(--ink-1); font-size: var(--fs-caption); text-align: right; }

.legal-details > summary {
  min-height: var(--touch-min);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--ink-2);
  font-size: var(--fs-sub);
  cursor: pointer;
  list-style: none;
}

.legal-details > summary::-webkit-details-marker { display: none; }
.sum-chev { width: 16px; height: 16px; flex: none; color: var(--ink-3); transition: transform 180ms ease; }
.legal-details[open] > summary .sum-chev { transform: rotate(180deg); }
.legal-body { padding: 2px 0 14px; }

.emphasis-block {
  margin-bottom: 16px;
  padding: 14px 16px;
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-ctl);
  background: var(--accent-soft);
  color: var(--accent-press);
  font-size: var(--fs-sub);
  font-weight: 600;
  line-height: 1.75;
}

.terms { margin-bottom: 20px; padding-left: 20px; color: var(--ink-2); font-size: var(--fs-caption); line-height: 1.8; }
.terms li { margin-bottom: 8px; }
.terms li:last-child { margin-bottom: 0; }
.terms strong { color: var(--ink-1); font-weight: 600; }
.agreement-lead { margin-bottom: 8px; color: var(--ink-2); font-size: var(--fs-caption); }
.agreements { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 9px; }
.agreement-link { color: var(--ink-2); font-size: var(--fs-caption); }
.link-sep { color: var(--line-strong); font-size: var(--fs-caption); font-style: normal; }

.agree-row {
  min-height: var(--touch-min);
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 14px;
  color: var(--ink-1);
  font-size: var(--fs-sub);
  cursor: pointer;
}

.agree-box {
  appearance: none;
  position: relative;
  width: 20px;
  height: 20px;
  flex: none;
  border: 1.5px solid var(--line-strong);
  border-radius: 5px;
  background: var(--surface);
  cursor: pointer;
}

.agree-box:checked { border-color: var(--accent); background: var(--accent); }
.agree-box:checked::after {
  content: '';
  position: absolute;
  left: 6px;
  top: 2px;
  width: 5px;
  height: 10px;
  border: solid var(--on-accent);
  border-width: 0 2px 2px 0;
  transform: rotate(45deg);
}

.consent-hint { margin: -2px 0 10px 30px; color: var(--ink-3); font-size: var(--fs-caption); }
.enter-btn { width: 100%; height: 48px; font-size: var(--fs-body); letter-spacing: 0.12em; transition: transform 180ms ease, background-color 180ms ease; }
.enter-btn:not(.is-disabled):hover { transform: translateY(-1px); }
.enter-btn:not(.is-disabled):active { transform: translateY(1px); }
.enter-error { margin-top: 10px; color: var(--danger); font-size: var(--fs-caption); line-height: 1.6; }

@media (max-width: 760px) {
  .start-page { padding: max(24px, env(safe-area-inset-top)) 20px max(28px, env(safe-area-inset-bottom)); }
  .start-layout { min-height: auto; grid-template-columns: minmax(0, 1fr); gap: 28px; }
  .start-intro { padding: 6px 0 0; }
  .brand-mark { width: 46px; height: 46px; }
  .mark-rail { left: 22px; top: 8px; bottom: 8px; }
  .mark-tick { left: 16px; }
  .mark-tick--one { top: 13px; }
  .mark-tick--two { top: 22px; }
  .mark-tick--three { top: 31px; }
  .mark-cursor { top: 18px; left: 18px; }
  .brand { font-size: 27px; }
  .intro-rule { width: 72%; margin: 16px 0 12px; }
  .tk-line { max-width: 13em; font-size: 26px; }
  .tk-lead { margin-top: 8px; font-size: var(--fs-sub); }
  .question-index { margin-top: 18px; }
  .tk-examples li { min-height: 42px; }
  .intro-footnote { margin-top: 16px; }
  .legal-card { padding: 16px 18px; }
  .legal-head { margin-bottom: 12px; }
  .legal-title { font-size: var(--fs-title); }
  .position-strip { align-items: center; padding: 9px 10px; }
  .strip-right { max-width: none; font-size: 11px; white-space: nowrap; }
  .legal-details > summary { min-height: 40px; }
  .agree-row { min-height: 40px; }
}

@media (max-width: 360px) {
  .start-page { padding-inline: 16px; }
  .legal-card { padding-inline: 14px; }
  .legal-head { gap: 8px; }
  .sec-badge { padding-inline: 6px; font-size: 9px; }
  .position-strip { align-items: flex-start; flex-direction: column; gap: 5px; }
  .strip-right { padding-left: 25px; text-align: left; }
}
</style>
