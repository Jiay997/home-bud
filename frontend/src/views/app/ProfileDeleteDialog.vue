<!--
  ProfileDeleteDialog SC-07 档案删除确认（Stitch 稿重构：底部抽屉）
  版式：标题（删除 X 的档案？/不可恢复警示）→ 删除范围级联单选卡（仅删除档案·推荐模式 /
  一并删除全部相关数据·彻底销毁）→ 默认保留说明灰卡 → 二次校验输入昵称（自动匹配绿勾）→
  红色不可恢复警示条 → 取消/确认删除双按钮 → 会员权益小字。
  删除走 body{mode, confirm_nickname}；删除当前对象时清空选中；成功后 emit deleted。
-->
<template>
  <Teleport to="body">
    <Transition name="pd-fade">
      <div v-if="modelValue" class="pd-overlay">
        <div class="pd-drawer" role="alertdialog" aria-modal="true" aria-label="删除档案确认">
          <!-- 标题区 -->
          <div class="pd-head">
            <p class="pd-title">删除 {{ displayName }} 的档案？</p>
            <p class="pd-warn">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M12 8.5v4m0 3v.5M10.3 3.9 2.6 17.5A2 2 0 0 0 4.3 20.5h15.4a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"
                  stroke="currentColor"
                  stroke-width="1.75"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
              删除后不可恢复，请谨慎操作。
            </p>
          </div>

          <!-- 删除范围级联单选 -->
          <p class="scope-lead">请选择删除范围</p>
          <div class="scope-cards">
            <label class="scope-card" :class="{ on: mode === 'profile_only' }">
              <i class="radio" />
              <span class="sc-main">
                <span class="sc-name">仅删除档案 <em class="badge green">推荐模式</em></span>
                <span class="sc-desc caption">说明：历史问答、测评报告保留，昵称脱敏为「{{ displayName }}」</span>
              </span>
              <input v-model="mode" type="radio" value="profile_only" class="sr-input" />
            </label>
            <label class="scope-card" :class="{ on: mode === 'with_history' }">
              <i class="radio" />
              <span class="sc-main">
                <span class="sc-name">一并删除全部相关数据 <em class="badge red">彻底销毁</em></span>
                <span class="sc-desc caption">说明：档案 + 问答 + 报告 + 图片</span>
              </span>
              <input v-model="mode" type="radio" value="with_history" class="sr-input" />
            </label>
          </div>

          <!-- 默认保留说明灰卡 -->
          <div class="keep-note">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" /><path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
            默认保留历史问答与测评报告，昵称脱敏为「{{ displayName }}」，不再关联档案。
          </div>

          <!-- 二次校验：孩子输入昵称 / 宠物输入类型（猫/狗） -->
          <div class="verify">
            <label class="verify-label">二次校验：输入{{ verifyHint }}</label>
            <div class="verify-box" :class="{ matched }">
              <input
                v-model="confirmNickname"
                class="verify-input"
                :placeholder="'请输入' + verifyHint"
                maxlength="20"
              />
              <svg v-if="matched" class="verify-check" viewBox="0 0 24 24" fill="none" aria-label="已匹配">
                <circle cx="12" cy="12" r="9" fill="var(--accent)" />
                <path d="m8.2 12.2 2.6 2.6 5-5.4" stroke="var(--sc-lowest)" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
            </div>
            <p v-if="matched" class="verify-tip caption">
              已自动匹配待操作档案名称，请核验无误后提交
            </p>
          </div>

          <!-- 红色警示条 -->
          <div class="danger-strip">!! 删除后不可恢复，无回收站。</div>

          <!-- 双按钮 -->
          <div class="pd-actions">
            <el-button size="large" class="btn-cancel" @click="cancel">取消</el-button>
            <el-button
              size="large"
              class="btn-del"
              :disabled="!matched"
              :loading="deleting"
              @click="doDelete"
            >
              确认删除
            </el-button>
          </div>

          <!-- 底部小字 -->
          <p class="pd-foot caption">会员档案删除后权益不退还</p>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { deleteChild, deletePet } from '@/api/client'
import { useUserStore } from '@/stores/user'

/**
 * 组件属性
 * @param modelValue 显隐（v-model）
 * @param profile 待删除档案对象
 * @param kind 档案类型 child | pet
 */
const props = defineProps<{
  modelValue: boolean
  profile: any
  kind: 'child' | 'pet'
}>()

/** 删除成功后触发（父组件刷新列表） */
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'deleted'): void
}>()

const user = useUserStore()

/** 级联模式：profile_only | with_history */
const mode = ref('profile_only')
/** 昵称校验输入 */
const confirmNickname = ref('')
/** 删除中 */
const deleting = ref(false)

/** 待删档案展示名：孩子用昵称；宠物用类型中文（后端宠物档案无昵称字段） */
const displayName = computed(() => {
  if (!props.profile) return ''
  if (props.kind === 'child') return props.profile.nickname || ''
  return props.profile.pet_type === 'dog' ? '狗' : '猫'
})

/** 二次校验提示词：孩子输入昵称，宠物输入类型中文 */
const verifyHint = computed(() => (props.kind === 'child' ? '昵称' : '宠物类型（猫/狗）'))

/** 二次校验匹配态（与待删档案展示名完全一致时放行提交） */
const matched = computed(
  () => !!props.profile && confirmNickname.value === displayName.value
)

/**
 * 打开时重置
 */
watch(
  () => props.modelValue,
  (v) => {
    if (v) {
      mode.value = 'profile_only'
      confirmNickname.value = ''
    }
  }
)

/**
 * 取消：关闭抽屉
 */
function cancel(): void {
  emit('update:modelValue', false)
}

/**
 * 执行删除
 * @throws 接口失败（含昵称校验不符）时消息提示
 */
async function doDelete(): Promise<void> {
  if (!props.profile) return
  deleting.value = true
  try {
    const body = { mode: mode.value, confirm_nickname: confirmNickname.value }
    if (props.kind === 'child') await deleteChild(props.profile.uid, body)
    else await deletePet(props.profile.uid, body)
    // 若删除的是当前对象，清空当前选择
    if (user.currentProfileUid === props.profile.uid) user.setCurrentProfile(null)
    ElMessage.success('档案已删除')
    emit('update:modelValue', false)
    emit('deleted')
  } catch (e: any) {
    ElMessage.error(e?.message || '删除失败，请重试')
  } finally {
    deleting.value = false
  }
}
</script>

<style lang="scss" scoped>
/* ---------- 遮罩 ---------- */
.pd-overlay {
  position: fixed;
  inset: 0;
  z-index: 2100;
  background: rgba(15, 30, 28, 0.5);
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

/* ---------- 抽屉 ---------- */
.pd-drawer {
  width: 100%;
  max-width: 430px; /* 与 MobileLayout 容器基准一致 */
  max-height: 88vh;
  overflow-y: auto;
  background: var(--surface);
  border-radius: 16px 16px 0 0;
  padding: var(--sp-6) var(--sp-6) calc(var(--sp-5) + env(safe-area-inset-bottom));
}

/* 标题区 */
.pd-head {
  margin-bottom: var(--sp-4);

  .pd-title {
    font-size: var(--fs-title);
    font-weight: 700;
    color: var(--ink-1);
  }

  .pd-warn {
    display: flex;
    align-items: center;
    gap: 5px;
    margin-top: 4px;
    font-size: var(--fs-caption);
    color: var(--warn);

    svg {
      width: 14px;
      height: 14px;
      flex: none;
    }
  }
}

/* 删除范围 */
.scope-lead {
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--ink-1);
  margin-bottom: var(--sp-3);
}

.scope-cards {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
}

.scope-card {
  position: relative;
  display: flex;
  gap: var(--sp-3);
  align-items: flex-start;
  border: 1px solid var(--line);
  border-radius: var(--radius-ctl);
  padding: var(--sp-4);
  cursor: pointer;

  &.on {
    border-color: var(--accent);
  }

  .radio {
    flex: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    border: 1.5px solid var(--line-strong);
    background: var(--surface);
    margin-top: 2px;
    position: relative;
  }

  &.on .radio {
    border-color: var(--accent);

    &::after {
      content: '';
      position: absolute;
      inset: 3px;
      border-radius: 50%;
      background: var(--accent);
    }
  }

  .sc-main {
    flex: 1;
    min-width: 0;
  }

  .sc-name {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);

    .badge {
      font-style: normal;
      font-size: 11px;
      font-weight: 600;
      padding: 0 8px;
      border-radius: 4px;

      &.green {
        background: var(--accent-soft);
        color: var(--accent);
      }

      &.red {
        background: var(--danger-soft);
        color: var(--danger);
      }
    }
  }

  .sc-desc {
    display: block;
    margin-top: 3px;
    line-height: 1.6;
  }

  .sr-input {
    position: absolute;
    opacity: 0;
    pointer-events: none;
  }
}

/* 默认保留说明灰卡 */
.keep-note {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  background: var(--sc-low);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);
  font-size: var(--fs-caption);
  color: var(--ink-2);
  line-height: 1.7;
  margin-bottom: var(--sp-5);

  svg {
    width: 14px;
    height: 14px;
    flex: none;
    margin-top: 4px;
    color: var(--ink-3);
  }
}

/* 二次校验 */
.verify {
  margin-bottom: var(--sp-4);

  .verify-label {
    display: block;
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);
    margin-bottom: var(--sp-2);
  }

  .verify-box {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    border: 1px solid var(--line);
    border-radius: var(--radius-ctl);
    padding: 0 var(--sp-3);
    height: 46px;
    background: var(--surface);

    &.matched {
      border-color: var(--accent);
    }

    .verify-input {
      flex: 1;
      min-width: 0;
      border: none;
      outline: none;
      background: none;
      font-size: var(--fs-sub);
      font-family: inherit;
      color: var(--ink-1);

      &::placeholder {
        color: var(--ink-3);
      }
    }

    .verify-check {
      width: 20px;
      height: 20px;
      flex: none;
    }
  }

  .verify-tip {
    margin-top: var(--sp-2);
    color: var(--accent);
  }
}

/* 红色警示条 */
.danger-strip {
  background: var(--danger-soft);
  border-radius: var(--radius-ctl);
  padding: var(--sp-3) var(--sp-4);
  font-size: var(--fs-sub);
  font-weight: 600;
  color: var(--danger);
  margin-bottom: var(--sp-5);
}

/* 双按钮 */
.pd-actions {
  display: flex;
  gap: var(--sp-3);

  .el-button {
    flex: 1;
  }

  .btn-cancel {
    font-weight: 600;
  }

  /* 确认删除：白底红边红字（危险描边态） */
  .btn-del {
    background: var(--surface);
    border: 1.5px solid var(--danger);
    color: var(--danger);
    font-weight: 700;

    &.is-disabled {
      background: var(--surface-2);
      border-color: var(--line);
      color: var(--ink-3);
    }
  }
}

/* 底部小字 */
.pd-foot {
  text-align: center;
  margin-top: var(--sp-4);
}

/* ---------- 过渡 ---------- */
.pd-fade-enter-active,
.pd-fade-leave-active {
  transition: opacity 0.2s ease;

  .pd-drawer {
    transition: transform 0.25s ease;
  }
}

.pd-fade-enter-from,
.pd-fade-leave-to {
  opacity: 0;

  .pd-drawer {
    transform: translateY(40px);
  }
}
</style>
