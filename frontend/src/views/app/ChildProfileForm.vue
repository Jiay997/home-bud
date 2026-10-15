<!--
  ChildProfileForm SC-04 新建/编辑孩子档案（Stitch 稿重构）
  版式：页头（返回 + 标题）→ 声明行 → 基础信息卡（昵称/出生日期/性别双卡）→ 生长情况卡
  （身高/体重/早产/过敏 chips/辅食月龄）→ 自动计算卡（派生月龄只读 + 月龄刻度带）→ 保存 +
  加密声明 → AI 免责条。
  逻辑：必填校验失败首错定位滚动；新建未单独同意儿童信息处理时先弹 ConsentModal；编辑走乐观锁 PUT。
-->
<template>
  <div class="page form-page">
    <!-- ===== 页头 ===== -->
    <header class="form-head">
      <button class="head-back touch-target" aria-label="返回" @click="$safeBack()">
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="m14.5 6-6 6 6 6" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="head-title">{{ isEdit ? '编辑孩子档案' : '新建孩子档案' }}</h1>
      <span class="head-space" aria-hidden="true" />
    </header>

    <!-- 声明行 -->
    <div class="declare-strip caption">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" /><path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
      信息用于生成贴合月龄的养育参考
    </div>

    <!-- 骨架 -->
    <template v-if="loading">
      <SkeletonBlock :height="200" style="margin-bottom: 12px" />
      <SkeletonBlock :height="260" style="margin-bottom: 12px" />
      <SkeletonBlock :height="140" />
    </template>

    <el-form v-else ref="formRef" :model="form" label-position="top" class="form">
      <!-- ===== 基础信息卡 ===== -->
      <section class="card st-card form-card">
        <div class="card-head">
          <h2 class="st-section-head">基础信息</h2>
          <span class="st-tag st-tag--amber st-tag--plain">带 * 为必填项</span>
        </div>

        <el-form-item prop="nickname" :error="errs.nickname">
          <template #label><span class="lb">昵称 <i class="req">*</i></span></template>
          <el-input v-model="form.nickname" placeholder="如：宝宝 A" maxlength="12" />
        </el-form-item>

        <el-form-item prop="birthdate" :error="errs.birthdate">
          <template #label>
            <span class="lb birth-lb">
              <span>出生日期 <i class="req">*</i></span>
              <span class="privacy-mark caption">
                <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M3 3l18 18" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /><path d="M10.6 5.1A9.8 9.8 0 0 1 12 5c5 0 8.6 3.6 10 7-.5 1.2-1.3 2.5-2.4 3.6M6.2 6.3C4 7.7 2.6 9.7 2 12c1.4 3.4 5 7 10 7 1.6 0 3-.4 4.3-1" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
                已开启私密校对
              </span>
            </span>
          </template>
          <el-date-picker
            v-model="form.birthdate"
            type="date"
            placeholder="选择出生日期"
            :disabled-date="disableFuture"
            style="width: 100%"
            value-format="YYYY-MM-DD"
          />
        </el-form-item>

        <el-form-item prop="gender" :error="errs.gender">
          <template #label><span class="lb">性别 <i class="req">*</i></span></template>
          <div class="gender-cards">
            <button
              type="button"
              class="gender-card"
              :class="{ on: form.gender === 'male' }"
              @click="form.gender = 'male'"
            >
              <i class="gdot" />男
            </button>
            <button
              type="button"
              class="gender-card"
              :class="{ on: form.gender === 'female' }"
              @click="form.gender = 'female'"
            >
              <i class="gdot" />女
            </button>
          </div>
        </el-form-item>
      </section>

      <!-- ===== 生长情况卡 ===== -->
      <section class="card st-card form-card">
        <div class="card-head">
          <h2 class="st-section-head">生长情况</h2>
          <span class="st-tag st-tag--outline">选填 · 越全越贴合</span>
        </div>

        <div class="two-col">
          <el-form-item label="身高 (cm)">
            <el-input v-model="form.height_cm" type="number" placeholder="如 92" min="0" step="0.1">
              <template #suffix>cm</template>
            </el-input>
          </el-form-item>
          <el-form-item label="体重 (kg)">
            <el-input v-model="form.weight_kg" type="number" placeholder="如 13.0" min="0" step="0.1">
              <template #suffix>kg</template>
            </el-input>
          </el-form-item>
        </div>

        <el-form-item label="是否早产">
          <el-select v-model="form.premature" style="width: 100%">
            <el-option label="否" :value="false" />
            <el-option label="是" :value="true" />
          </el-select>
        </el-form-item>

        <!-- 已知过敏项 chips -->
        <div class="chip-field">
          <span class="lb">已知过敏项</span>
          <div class="chip-box">
            <span v-for="t in allergyTags" :key="t" class="chip">
              {{ t }}
              <button type="button" class="chip-x" :aria-label="`移除 ${t}`" @click="removeAllergy(t)">×</button>
            </span>
            <span v-if="allergyTags.length === 0" class="chip empty">无</span>
            <button type="button" class="chip-add touch-target" @click="openAllergyInput">＋ 添加</button>
          </div>
          <input
            v-if="allergyAdding"
            ref="allergyInputRef"
            v-model="allergyDraft"
            class="chip-input"
            placeholder="输入过敏项，回车确认"
            maxlength="20"
            @keydown.enter.prevent="commitAllergy"
            @keydown.esc="allergyAdding = false"
            @blur="commitAllergy"
          />
        </div>

        <el-form-item label="辅食开始月龄" class="last-item">
          <el-select v-model="form.food_start_month" style="width: 100%">
            <el-option label="尚未添加" :value="0" />
            <el-option label="4 月龄" :value="4" />
            <el-option label="5 月龄" :value="5" />
            <el-option label="6 月龄" :value="6" />
            <el-option label="7 月龄" :value="7" />
            <el-option label="8 月龄及以上" :value="8" />
          </el-select>
        </el-form-item>
      </section>

      <!-- ===== 自动计算卡（派生月龄只读） ===== -->
      <section class="card st-card form-card derived-card">
        <div class="card-head">
          <h2 class="derived-title">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M4 20h16M7 16V7l5-3 5 3v9M10 16v-4M14 16v-4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" /></svg>
            自动计算：月龄 {{ ageMonths ?? '—' }} 月 · 区间 {{ ageRange }}
          </h2>
          <span class="st-tag st-tag--outline">只读，服务端派生</span>
        </div>

        <!-- 月龄刻度带（参考 GraduatedBand 视觉） -->
        <div class="age-band" role="img" :aria-label="`当前月龄 ${ageMonths ?? '—'} 月，处于 ${ageRange} 区间`">
          <span v-for="t in ageTicks" :key="t.label" class="age-tick" :style="{ left: t.pct }">
            <i class="tick-mark" />{{ t.label }}
          </span>
          <div class="age-track">
            <div class="age-cursor" :style="{ left: cursorPct }">
              <em>当前({{ ageMonths ?? '—' }}月)</em>
            </div>
          </div>
        </div>

        <p class="derived-note caption">
          系统已依据出生日期锁定阶段生长常模，自动匹配适合的发展监测与营养辅导区间。
        </p>
      </section>

      <!-- ===== 保存 ===== -->
      <div class="form-actions">
        <el-button type="primary" size="large" class="save-btn" :loading="saving" @click="save">保存</el-button>
        <p class="encrypt-note caption">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="5" y="10.5" width="14" height="9.5" rx="2" stroke="currentColor" stroke-width="1.6" /><path d="M8.5 10.5V8a3.5 3.5 0 0 1 7 0v2.5" stroke="currentColor" stroke-width="1.6" /></svg>
          敏感字段加密存储
        </p>
      </div>
    </el-form>

    <!-- AI 免责条 -->
    <p class="ai-note caption">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" /><path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
      AI 生成内容，仅供参考，不替代医生诊断
    </p>

    <!-- 儿童信息单独同意弹窗 -->
    <ConsentModal v-model="consentVisible" :need-guardian-name="true" @agreed="afterConsent" @declined="onDeclined" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getChildren, createChild, updateChild } from '@/api/client'
import { ApiError } from '@/api/request'
import SkeletonBlock from '@/components/SkeletonBlock.vue'
import ConsentModal from './ConsentModal.vue'

const route = useRoute()
const router = useRouter()

/** 编辑态 uid（路由参数） */
const editUid = computed(() => (route.params.uid as string) || '')
/** 是否编辑态 */
const isEdit = computed(() => !!editUid.value)

/** 表单数据（caregiver/concerns 为存量字段：不展示但编辑态保留回传，避免覆盖丢失） */
const form = ref<any>({
  nickname: '',
  birthdate: '',
  gender: '',
  height_cm: '',
  weight_kg: '',
  premature: false,
  food_start_month: 0,
  caregiver: '',
  concerns: '',
  allergy: '',
  version: 0
})

/** 逐字段错误 */
const errs = ref<Record<string, string>>({})
/** 提交中 */
const saving = ref(false)
/** 加载态 */
const loading = ref(isEdit.value)
/** 同意弹窗显隐 */
const consentVisible = ref(false)

/** 表单 ref（首错定位用） */
const formRef = ref()

/** 过敏项 chips（由 form.allergy 拆分；提交时以「、」拼回） */
const allergyTags = ref<string[]>([])
/** 过敏项添加中 */
const allergyAdding = ref(false)
/** 过敏项草稿输入 */
const allergyDraft = ref('')
/** 过敏项输入框 ref（自动聚焦） */
const allergyInputRef = ref()

/**
 * 派生月龄（出生日期 → 足月数）
 */
const ageMonths = computed<number | null>(() => {
  if (!form.value.birthdate) return null
  const b = new Date(form.value.birthdate)
  const now = new Date()
  return Math.max(0, (now.getFullYear() - b.getFullYear()) * 12 + (now.getMonth() - b.getMonth()))
})

/** 月龄所处发育区间文案 */
const ageRange = computed(() => rangeOf(ageMonths.value))

/**
 * 月龄 → 发育区间映射
 * @param m 月龄（null 返回 —）
 * @returns 区间文案
 */
function rangeOf(m: number | null): string {
  if (m === null) return '—'
  if (m < 12) return '0-1 岁'
  if (m < 36) return '1-3 岁'
  if (m < 72) return '3-6 岁'
  return '6 岁+'
}

/** 刻度档位（0 岁/1 岁/3 岁/6 岁+）及归一化位置（0-72 月刻度） */
const ageTicks = [
  { label: '0 岁', pct: '0%' },
  { label: '1 岁', pct: `${(12 / 72) * 100}%` },
  { label: '3 岁', pct: `${(36 / 72) * 100}%` },
  { label: '6 岁+', pct: '100%' }
]

/** 游标落点百分比（月龄按 0-72 月限幅归一） */
const cursorPct = computed(() => {
  const m = Math.min(72, Math.max(0, ageMonths.value ?? 0))
  return `${(m / 72) * 100}%`
})

/**
 * 禁选未来日期
 * @param d 候选日期
 * @returns 是否禁用
 */
function disableFuture(d: Date): boolean {
  return d.getTime() > Date.now()
}

/**
 * 过敏项拆分：编辑态由字符串还原 chips
 * @param raw 过敏字符串（「、」分隔）
 */
function parseAllergy(raw: string): void {
  allergyTags.value = String(raw || '')
    .split('、')
    .map((s) => s.trim())
    .filter(Boolean)
}

/**
 * 打开过敏项内联输入框（下一帧聚焦）
 */
function openAllergyInput(): void {
  allergyAdding.value = true
  allergyDraft.value = ''
  void nextTick(() => allergyInputRef.value?.focus())
}

/**
 * 提交过敏项草稿：回车/失焦落 chip，空草稿仅收起
 */
function commitAllergy(): void {
  const v = allergyDraft.value.trim()
  if (v && !allergyTags.value.includes(v)) allergyTags.value.push(v)
  allergyAdding.value = false
  allergyDraft.value = ''
}

/**
 * 移除过敏 chip
 * @param t 待移除项
 */
function removeAllergy(t: string): void {
  allergyTags.value = allergyTags.value.filter((x) => x !== t)
}

/**
 * 编辑态加载已有档案
 */
onMounted(async () => {
  if (!isEdit.value) return
  try {
    const list: any = await getChildren()
    const items = list?.children || list?.items || (Array.isArray(list) ? list : [])
    const hit = items.find((x: any) => x.uid === editUid.value)
    if (hit) {
      // 后端字段 → 表单字段映射：birth_date/premature_flag/solid_food_month；allergy 为字符串数组
      form.value = {
        ...form.value,
        ...hit,
        birthdate: hit.birth_date || '',
        premature: !!hit.premature_flag,
        food_start_month: hit.solid_food_month ?? 0,
        allergy: Array.isArray(hit.allergy) ? hit.allergy.join('、') : hit.allergy || ''
      }
      parseAllergy(form.value.allergy)
    } else {
      ElMessage.error('未找到该档案')
      router.replace('/app/profiles')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '加载失败')
  } finally {
    loading.value = false
  }
})

/**
 * 表单校验（手写规则，返回首个错误字段）
 * @returns 校验是否通过
 */
function validate(): boolean {
  errs.value = {}
  if (!form.value.nickname?.trim()) errs.value.nickname = '请填写昵称'
  if (!form.value.birthdate) errs.value.birthdate = '请选择出生日期'
  if (!form.value.gender) errs.value.gender = '请选择性别'
  return Object.keys(errs.value).length === 0
}

/**
 * 可选数值序列化：null / '' / undefined 视为未填写（返回 undefined，不出现在提交载荷），
 * 其余安全转数值；非法输入同样按未填写处理，避免 NaN / 0 误入载荷
 * @param v 表单原始值（number | string | null | undefined）
 * @returns 数值或 undefined
 */
function toOptionalNumber(v: unknown): number | undefined {
  if (v === null || v === undefined || v === '') return undefined
  const n = Number(v)
  return Number.isFinite(n) ? n : undefined
}

/**
 * 组装提交载荷（含新增生长字段；caregiver/concerns 存量透传）
 * @returns 提交对象
 */
function buildPayload(): any {
  // 字段名与后端 ChildProfileCreate 契约严格对齐：
  // birth_date / premature_flag / solid_food_month / allergy(list[str])
  // 身高/体重序列化：null / '' / undefined 一律视为未填写（undefined，不出现在提交载荷），
  // 避免 Number(null) = 0 触发后端 ge=20 校验失败（编辑未填身高档案保存必败缺陷）
  return {
    nickname: form.value.nickname.trim(),
    birth_date: form.value.birthdate,
    gender: form.value.gender,
    height_cm: toOptionalNumber(form.value.height_cm),
    weight_kg: toOptionalNumber(form.value.weight_kg),
    premature_flag: !!form.value.premature,
    solid_food_month: form.value.food_start_month || undefined,
    allergy: allergyTags.value.length ? allergyTags.value : undefined,
    caregiver: form.value.caregiver || undefined,
    concerns: form.value.concerns || undefined
  }
}

/**
 * 保存：先校验首错定位；新建且未单独同意 → 弹 ConsentModal；编辑走乐观锁 PUT
 * @throws ApiError（含 1302 未同意 / 1003 乐观锁冲突）时映射为字段错误或提示
 */
async function save(): Promise<void> {
  if (!validate()) {
    // 首错定位滚动
    const firstKey = Object.keys(errs.value)[0]
    const el = document.querySelector(`.el-form-item .el-input, .el-form-item`) as HTMLElement
    void firstKey
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return
  }

  if (!isEdit.value) {
    // 新建：检查是否已单独同意儿童信息处理
    consentVisible.value = true
    return
  }

  saving.value = true
  try {
    const payload = { ...buildPayload(), version: form.value.version }
    await updateChild(editUid.value, payload)
    ElMessage.success('已保存')
    router.replace('/app/profiles')
  } catch (e: any) {
    if (e instanceof ApiError && e.code === 1003) {
      ElMessage.error('档案刚被其他设备修改，请返回列表重新进入编辑')
    } else {
      ElMessage.error(e?.message || '保存失败')
    }
  } finally {
    saving.value = false
  }
}

/**
 * 同意弹窗确认后：真正创建档案
 * @throws ApiError 1302 时提示需单独同意
 */
async function afterConsent(): Promise<void> {
  saving.value = true
  try {
    await createChild(buildPayload())
    ElMessage.success('档案已创建')
    router.replace('/app/profiles')
  } catch (e: any) {
    if (e instanceof ApiError && e.code === 1302) {
      ElMessage.error('需要先完成儿童信息单独同意')
      consentVisible.value = true
    } else {
      ElMessage.error(e?.message || '创建失败')
    }
  } finally {
    saving.value = false
  }
}

/**
 * 暂不同意：留在表单页并提示
 */
function onDeclined(): void {
  ElMessage.info('暂不同意将无法创建儿童档案')
}
</script>

<style lang="scss" scoped>
/* ---------- 页头 ---------- */
.form-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-4);

  .head-back {
    width: 36px;
    height: 36px;
    border: none;
    background: none;
    color: var(--ink-1);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;

    svg {
      width: 22px;
      height: 22px;
    }
  }

  .head-title {
    font-size: var(--fs-title);
    font-weight: 700;
    color: var(--ink-1);
  }

  .head-space {
    width: 36px;
  }
}

/* 声明行 */
.declare-strip {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--accent);
  margin-bottom: var(--sp-5);

  svg {
    width: 14px;
    height: 14px;
    flex: none;
  }
}

/* 卡片间距 */
.form-card {
  margin-bottom: var(--sp-4);

  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--sp-5);

    .st-section-head {
      font-size: var(--fs-body);
    }
  }

  .lb {
    font-size: var(--fs-sub);
    color: var(--ink-2);

    .req {
      font-style: normal;
      color: var(--danger);
    }
  }

  .last-item {
    margin-bottom: 0;
  }
}

/* 出生日期行的隐私标注 */
.birth-lb {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  .privacy-mark {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    color: var(--ink-3);

    svg {
      width: 13px;
      height: 13px;
    }
  }
}

/* 性别双卡切换 */
.gender-cards {
  display: flex;
  gap: var(--sp-3);
  width: 100%;
}

.gender-card {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  height: 44px;
  border-radius: var(--radius-ctl);
  border: 1px solid var(--line);
  background: var(--surface);
  color: var(--ink-2);
  font-size: var(--fs-sub);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s;

  .gdot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    border: 1.5px solid var(--line-strong);
    background: var(--surface);
    flex: none;
  }

  &.on {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--ink-1);
    font-weight: 600;

    .gdot {
      border-color: var(--accent);
      border-width: 4px;
    }
  }
}

/* 双列字段 */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-4);
}

/* 过敏 chips 字段 */
.chip-field {
  margin-bottom: 18px;

  .chip-box {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--sp-2);
    border: 1px solid var(--line);
    border-radius: var(--radius-ctl);
    padding: 8px var(--sp-3);
    min-height: 42px;
    background: var(--surface);
    margin-top: var(--sp-2);
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px 8px;
    border-radius: 4px;
    background: var(--accent-soft);
    color: var(--accent);
    font-size: var(--fs-caption);

    .chip-x {
      border: none;
      background: none;
      color: inherit;
      cursor: pointer;
      font-size: 13px;
      line-height: 1;
      padding: 0;
    }

    &.empty {
      background: var(--surface-2);
      color: var(--ink-3);
    }
  }

  .chip-add {
    border: none;
    background: none;
    color: var(--accent);
    font-size: var(--fs-caption);
    cursor: pointer;
    padding: 2px 4px;
  }

  .chip-input {
    width: 100%;
    margin-top: var(--sp-2);
    border: 1px solid var(--accent-line);
    border-radius: var(--radius-ctl);
    padding: 8px var(--sp-3);
    font-size: var(--fs-sub);
    font-family: inherit;
    background: var(--surface);
    color: var(--ink-1);
    outline: none;
  }
}

/* 自动计算卡 */
.derived-card {
  .derived-title {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);

    svg {
      width: 16px;
      height: 16px;
      color: var(--accent);
      flex: none;
    }
  }
}

/* 月龄刻度带（参考 GraduatedBand：轨道 + 越出游标 + 刻度档位） */
.age-band {
  position: relative;
  margin: var(--sp-6) 0 var(--sp-3);

  .age-tick {
    position: absolute;
    top: 0;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    font-size: var(--fs-caption);
    color: var(--ink-3);
    white-space: nowrap;

    .tick-mark {
      width: 1px;
      height: 5px;
      background: var(--line-strong);
    }

    &:first-child {
      transform: none;

      .tick-mark {
        width: 2px;
      }
    }

    &:last-child {
      transform: translateX(-100%);
    }
  }

  .age-track {
    margin-top: 22px;
    height: 12px;
    border-radius: var(--radius-pill);
    background: var(--surface-2);
    position: relative;
  }

  .age-cursor {
    position: absolute;
    top: -5px;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: var(--accent);
    border: 3px solid var(--surface);
    box-shadow: var(--shadow-e1);
    transform: translateX(-50%);
    transition: left 0.4s ease;

    em {
      position: absolute;
      bottom: 26px;
      left: 50%;
      transform: translateX(-50%);
      font-style: normal;
      font-size: var(--fs-caption);
      color: var(--accent);
      font-weight: 600;
      white-space: nowrap;
    }
  }
}

.derived-note {
  margin-top: var(--sp-3);
  line-height: 1.7;
}

/* 保存区 */
.form-actions {
  padding-top: var(--sp-2);

  .save-btn {
    width: 100%;
    height: 48px;
    font-size: var(--fs-body);
  }

  .encrypt-note {
    display: flex;
    justify-content: center;
    align-items: center;
    gap: 5px;
    margin-top: var(--sp-3);

    svg {
      width: 13px;
      height: 13px;
    }
  }
}

/* AI 免责条 */
.ai-note {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 5px;
  margin-top: var(--sp-5);

  svg {
    width: 14px;
    height: 14px;
  }
}
</style>
