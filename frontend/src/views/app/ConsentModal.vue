<!--
  ConsentModal SC-06 儿童信息处理告知与单独同意（Stitch 稿重构：底部抽屉）
  版式：遮罩置灰 + 底部抽屉白卡（拖拽条/X 关闭 + 「儿童隐私保护说明」绿标）→
  五段告知行卡（目的/字段/期限/共享/权利）→ 监护声明绿条（可点击确认）→ 单独同意勾选 →
  监护人姓名（needGuardianName 存证）→ 暂不同意/同意并继续双按钮 → 底部「暂不同意不落库」小字。
  同意成功后 emit agreed；拒绝则关闭并 emit declined。
-->
<template>
  <Teleport to="body">
    <Transition name="cm-fade">
      <div v-if="modelValue" class="cm-overlay">
          <div class="cm-drawer" role="dialog" aria-modal="true" aria-label="儿童信息处理告知与单独同意">
            <!-- 拖拽条（装饰） -->
            <i class="grabber" aria-hidden="true" />

            <!-- 抽屉头：绿标 + 标题 + 关闭 -->
            <div class="cm-head">
              <div class="cm-titles">
                <p class="cm-eyebrow">● 儿童隐私保护说明</p>
                <h3 class="cm-title">儿童信息处理告知与单独同意</h3>
              </div>
              <button class="cm-close" aria-label="关闭" @click="close">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="m6 6 12 12M18 6 6 18" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" />
                </svg>
              </button>
            </div>

            <!-- 五段告知行卡 -->
            <div class="cm-notice">
              <div v-for="s in sections" :key="s.title" class="notice-row">
                <span class="nr-title"><i class="nr-bar" />{{ s.title }}</span>
                <p class="nr-body">
                  <template v-if="s.link">{{ s.text }}<a class="nr-link" href="javascript:void(0)">{{ s.link }}</a></template>
                  <template v-else>{{ s.text }}</template>
                </p>
              </div>
            </div>

            <!-- 监护声明绿条（点击确认声明） -->
            <button type="button" class="guard-strip" :class="{ on: declared }" @click="declared = !declared">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 3 5 5.5v6c0 4.5 3 7.9 7 9.5 4-1.6 7-5 7-9.5v-6L12 3Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
                <path d="m9 11.5 2.2 2.2L15.5 9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <span class="gs-text"><strong>监护声明：</strong>本人为法定监护人</span>
              <i class="gs-check" :class="{ on: declared }" />
            </button>

            <!-- 单独同意勾选 -->
            <label class="consent-row">
              <input v-model="consented" type="checkbox" class="cm-box" />
              <span>已阅读并单独同意处理上述儿童信息</span>
            </label>

            <!-- 监护人姓名（同意记录存证） -->
            <div v-if="needGuardianName" class="guardian-name">
              <label class="gn-label caption">监护人姓名（用于同意记录存证）</label>
              <el-input v-model="guardianName" placeholder="请输入监护人真实姓名" maxlength="20" />
            </div>

            <!-- 双按钮 -->
            <div class="cm-actions">
              <el-button size="large" class="btn-decline" @click="decline">暂不同意</el-button>
              <el-button
                type="primary"
                size="large"
                class="btn-agree"
                :disabled="!canSubmit"
                :loading="submitting"
                @click="agree"
              >
                同意并继续 →
              </el-button>
            </div>

            <!-- 底部小字 -->
            <p class="cm-foot caption">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" /><path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
              “暂不同意”：不落库，可继续浏览通用内容
            </p>
          </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { agreeConsent } from '@/api/client'

/**
 * 组件属性
 * @param modelValue 显隐（v-model）
 * @param needGuardianName 是否要求监护人姓名（单独同意存证）
 */
const props = defineProps<{
  modelValue: boolean
  needGuardianName?: boolean
}>()

/** 同意成功 */
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'agreed'): void
  (e: 'declined'): void
}>()

/** 五段告知文案（稿面：目的/字段/期限/共享/权利） */
const sections = [
  { title: '目的', text: '生成贴合月龄的养育参考' },
  { title: '字段', text: '昵称、出生日期、性别、身高、体重、早产标记、过敏项、辅食月龄' },
  { title: '期限', text: '账号存续期 + 30 天' },
  { title: '共享', text: '仅本产品推理，不用于训练，详见', link: '《第三方共享清单》' },
  { title: '权利', text: '查阅 / 更正 / 导出 / 撤回 / 删除（我的 → 个人信息权利中心）' }
]

/** 监护人声明勾选（绿条载体） */
const declared = ref(false)
/** 单独同意勾选 */
const consented = ref(false)
/** 监护人姓名 */
const guardianName = ref('')
/** 提交中 */
const submitting = ref(false)

/** 可提交条件：监护声明 + 单独同意（+ 监护人姓名，需要时） */
const canSubmit = computed(
  () => declared.value && consented.value && (!props.needGuardianName || !!guardianName.value.trim())
)

/**
 * 弹窗打开时重置勾选与姓名
 */
watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      declared.value = false
      consented.value = false
      guardianName.value = ''
    }
  }
)

/**
 * 关闭抽屉（X 按钮）：等同暂不操作，仅收起
 */
function close(): void {
  emit('update:modelValue', false)
}

/**
 * 同意提交 child_info 类型同意
 * @throws 接口失败时消息提示并保持抽屉
 */
async function agree(): Promise<void> {
  submitting.value = true
  try {
    await agreeConsent('child_personal_info', props.needGuardianName ? guardianName.value.trim() : undefined)
    ElMessage.success('已记录你的同意')
    emit('agreed')
    emit('update:modelValue', false)
  } catch (e: any) {
    ElMessage.error(e?.message || '提交失败，请重试')
  } finally {
    submitting.value = false
  }
}

/**
 * 暂不同意：关闭抽屉并通知父级
 */
function decline(): void {
  emit('declined')
  emit('update:modelValue', false)
}
</script>

<style lang="scss" scoped>
/* ---------- 遮罩 ---------- */
.cm-overlay {
  position: fixed;
  inset: 0;
  z-index: 2100;
  background: rgba(15, 30, 28, 0.5);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

/* ---------- 抽屉 ---------- */
.cm-drawer {
  width: 100%;
  max-width: 430px; /* 与 MobileLayout 容器基准一致 */
  max-height: 88vh;
  overflow-y: auto;
  background: var(--surface);
  border-radius: 16px 16px 0 0;
  padding: var(--sp-3) var(--sp-6) calc(var(--sp-5) + env(safe-area-inset-bottom));
}

.grabber {
  display: block;
  width: 44px;
  height: 4px;
  border-radius: var(--radius-pill);
  background: var(--line-strong);
  margin: 0 auto var(--sp-4);
}

/* 抽屉头 */
.cm-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--line);
  margin-bottom: var(--sp-4);

  .cm-eyebrow {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: var(--accent);
    font-family: var(--font-numeric);
  }

  .cm-title {
    margin-top: 4px;
    font-size: var(--fs-title);
    font-weight: 700;
    color: var(--ink-1);
  }

  .cm-close {
    width: 32px;
    height: 32px;
    flex: none;
    border: none;
    background: none;
    color: var(--ink-2);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;

    svg {
      width: 20px;
      height: 20px;
    }
  }
}

/* 五段告知行卡 */
.cm-notice {
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  overflow: hidden;
  margin-bottom: var(--sp-4);

  .notice-row {
    display: grid;
    grid-template-columns: 76px 1fr;
    gap: var(--sp-3);
    padding: var(--sp-4);

    & + .notice-row {
      border-top: 1px solid var(--line);
    }

    .nr-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: var(--fs-caption);
      font-weight: 700;
      color: var(--ink-1);

      .nr-bar {
        flex: none;
        width: 6px;
        height: 6px;
        border-radius: 1px;
        background: var(--accent);
      }
    }

    .nr-body {
      font-size: var(--fs-caption);
      color: var(--ink-2);
      line-height: 1.7;

      .nr-link {
        color: var(--accent);
        text-decoration: underline;
        text-underline-offset: 3px;
        margin-left: 2px;
      }
    }
  }
}

/* 监护声明绿条 */
.guard-strip {
  width: 100%;
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  background: var(--accent-soft);
  border: 1px solid var(--accent-line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-4);
  cursor: pointer;
  margin-bottom: var(--sp-4);
  text-align: left;

  svg {
    width: 18px;
    height: 18px;
    color: var(--accent);
    flex: none;
  }

  .gs-text {
    flex: 1;
    min-width: 0;
    font-size: var(--fs-sub);
    color: var(--ink-2);

    strong {
      color: var(--ink-1);
      font-weight: 600;
    }
  }

  .gs-check {
    flex: none;
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1.5px solid var(--line-strong);
    background: var(--surface);
    position: relative;

    &.on {
      background: var(--accent);
      border-color: var(--accent);

      &::after {
        content: '';
        position: absolute;
        left: 5px;
        top: 1px;
        width: 5px;
        height: 10px;
        border: solid var(--sc-lowest);
        border-width: 0 2px 2px 0;
        transform: rotate(45deg);
      }
    }
  }
}

/* 单独同意勾选行 */
.consent-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  font-size: var(--fs-sub);
  color: var(--ink-1);
  cursor: pointer;
  margin-bottom: var(--sp-4);

  .cm-box {
    appearance: none;
    width: 18px;
    height: 18px;
    flex: none;
    border: 1.5px solid var(--line-strong);
    border-radius: 4px;
    background: var(--surface);
    cursor: pointer;
    position: relative;

    &:checked {
      background: var(--accent);
      border-color: var(--accent);

      &::after {
        content: '';
        position: absolute;
        left: 5px;
        top: 1px;
        width: 5px;
        height: 10px;
        border: solid var(--sc-lowest);
        border-width: 0 2px 2px 0;
        transform: rotate(45deg);
      }
    }
  }
}

/* 监护人姓名存证 */
.guardian-name {
  margin-bottom: var(--sp-4);

  .gn-label {
    display: block;
    margin-bottom: var(--sp-2);
  }
}

/* 双按钮 */
.cm-actions {
  display: flex;
  gap: var(--sp-3);

  .el-button {
    flex: 1;
  }

  .btn-decline {
    font-weight: 600;
  }

  .btn-agree {
    font-weight: 600;
  }
}

/* 底部小字 */
.cm-foot {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 5px;
  margin-top: var(--sp-4);

  svg {
    width: 13px;
    height: 13px;
  }
}

/* ---------- 过渡 ---------- */
.cm-fade-enter-active,
.cm-fade-leave-active {
  transition: opacity 0.2s ease;

  .cm-drawer {
    transition: transform 0.25s ease;
  }
}

.cm-fade-enter-from,
.cm-fade-leave-to {
  opacity: 0;

  .cm-drawer {
    transform: translateY(40px);
  }
}
</style>
