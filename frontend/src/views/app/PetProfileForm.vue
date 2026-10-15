<!--
  PetProfileForm SC-05 新建/编辑宠物档案（Stitch 稿重构）
  版式：页头 → 档案校准进度条（真实完备度）→ 基本信息卡（类型猫/狗双卡/品种联动下拉/年龄/绝育）→
  状态卡（体重+标准体态参考/主要食物）→ 多智能体家庭协同联动卡（有孩子档案时已激活）→
  ✓ 保存 + MVP 声明 → AI 免责条。
  逻辑：类型/年龄必填校验；品种猫/狗联动；年龄下拉映射 age_band（junior/adult/senior）；编辑走乐观锁 PUT。
  字段契约（数据模型 V1.1）：pet_type/breed/age_band/neutered_flag/weight_kg/main_food。
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
      <h1 class="head-title">{{ isEdit ? '编辑宠物档案' : '新建宠物档案' }}</h1>
      <span class="head-space" aria-hidden="true" />
    </header>

    <!-- ===== 档案校准进度条 ===== -->
    <div class="card calib-card">
      <div class="calib-head">
        <span class="calib-label"><i class="dot" /> 档案校准进度 · 步骤 1/1</span>
        <span class="calib-pct numeric">{{ completenessPct }}% 完备</span>
      </div>
      <div class="st-meter">
        <div class="st-meter__fill" :style="{ width: completenessPct + '%' }" />
      </div>
      <div class="calib-steps caption">
        <span>基础识别</span><span>饲养基准</span><span>安全矩阵</span>
      </div>
    </div>

    <!-- 骨架 -->
    <template v-if="loading">
      <SkeletonBlock :height="240" style="margin-bottom: 12px" />
      <SkeletonBlock :height="160" />
    </template>

    <el-form v-else :model="form" label-position="top" class="form">
      <!-- ===== 基本信息卡 ===== -->
      <section class="card st-card form-card">
        <div class="card-head">
          <h2 class="st-section-head">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="7.2" cy="9.5" r="1.7" fill="currentColor" /><circle cx="12" cy="7.5" r="1.7" fill="currentColor" /><circle cx="16.8" cy="9.5" r="1.7" fill="currentColor" /><path d="M12 11c2.3 0 4.2 1.8 4.2 3.8 0 1.4-1 2.4-2.3 2.4-.7 0-1.2-.3-1.9-.3s-1.2.3-1.9.3c-1.3 0-2.3-1-2.3-2.4 0-2 1.9-3.8 4.2-3.8Z" fill="currentColor" /></svg>
            基本信息
          </h2>
          <span class="req-mark">* 为必填项</span>
        </div>

        <el-form-item required :error="errs.species">
          <template #label><span class="lb">类型 <i class="req">*</i></span></template>
          <div class="species-cards">
            <button type="button" class="sp-card" :class="{ on: form.species === 'cat' }" @click="switchSpecies('cat')">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <circle cx="7.2" cy="9.5" r="1.7" fill="currentColor" />
                <circle cx="12" cy="7.5" r="1.7" fill="currentColor" />
                <circle cx="16.8" cy="9.5" r="1.7" fill="currentColor" />
                <path d="M12 11c2.3 0 4.2 1.8 4.2 3.8 0 1.4-1 2.4-2.3 2.4-.7 0-1.2-.3-1.9-.3s-1.2.3-1.9.3c-1.3 0-2.3-1-2.3-2.4 0-2 1.9-3.8 4.2-3.8Z" fill="currentColor" />
              </svg>
              猫
            </button>
            <button type="button" class="sp-card" :class="{ on: form.species === 'dog' }" @click="switchSpecies('dog')">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M5 9c0-2 1-3.5 2.2-3.5S9.5 7 9.5 9c0 .8-.2 1.5-.6 2L12 12l3.1-1c-.4-.5-.6-1.2-.6-2 0-2 1-3.5 2.3-3.5S19 7 19 9c0 1.3-.4 2.4-1.2 2.9l.7 3.6c.3 1.6-.7 3-2.3 3H7.8c-1.6 0-2.6-1.4-2.3-3l.7-3.6C5.4 11.4 5 10.3 5 9Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" />
              </svg>
              狗
            </button>
          </div>
        </el-form-item>

        <el-form-item label="品种（可搜索，不确定可选「不确定」）">
          <el-select v-model="form.breed" filterable placeholder="输入或选择品种" style="width: 100%">
            <el-option label="不确定" value="unknown" />
            <el-option v-for="b in breedOptions" :key="b" :label="b" :value="b" />
          </el-select>
        </el-form-item>

        <el-form-item required :error="errs.age">
          <template #label><span class="lb">年龄 <i class="req">*</i></span></template>
          <el-select v-model="ageSel" placeholder="选择年龄" style="width: 100%">
            <el-option v-for="o in AGE_OPTIONS" :key="o.v" :label="o.label" :value="o.v" />
          </el-select>
        </el-form-item>

        <el-form-item label="绝育状态" class="last-item">
          <el-select v-model="form.sterilized" style="width: 100%">
            <el-option label="已绝育" :value="true" />
            <el-option label="未绝育" :value="false" />
            <el-option label="不详" :value="null" />
          </el-select>
        </el-form-item>
      </section>

      <!-- ===== 状态卡 ===== -->
      <section class="card st-card form-card">
        <div class="card-head">
          <h2 class="st-section-head">
            <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><rect x="4" y="8" width="16" height="12" rx="2.5" stroke="currentColor" stroke-width="1.6" /><path d="M8.5 8a3.5 3.5 0 0 1 7 0" stroke="currentColor" stroke-width="1.6" /><path d="M12 11v5" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" /></svg>
            状态
          </h2>
          <span class="st-tag st-tag--outline">选填 · 用于饲养规划</span>
        </div>

        <el-form-item>
          <template #label>
            <span class="lb weight-lb">
              <span>体重</span>
              <span class="caption weight-ref">标准体态刻度参考: {{ weightRef }}</span>
            </span>
          </template>
          <el-input v-model="form.weight_kg" type="number" placeholder="如 4.2" min="0.1" max="100" step="0.1">
            <template #suffix>kg</template>
          </el-input>
        </el-form-item>

        <el-form-item label="主要食物" class="last-item">
          <el-select v-model="form.food" style="width: 100%">
            <el-option v-for="f in foodOptions" :key="f" :label="f" :value="f" />
          </el-select>
        </el-form-item>
      </section>

      <!-- ===== 多智能体家庭协同联动卡 ===== -->
      <section class="synergy-card" :class="{ active: hasChildren }">
        <span class="sy-ico" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none">
            <path d="M12 3 5 5.5v6c0 4.5 3 7.9 7 9.5 4-1.6 7-5 7-9.5v-6L12 3Z" stroke="currentColor" stroke-width="1.75" stroke-linejoin="round" />
            <path d="m9 11.5 2.2 2.2L15.5 9" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </span>
        <div class="sy-text">
          <p class="sy-title">
            多智能体家庭协同联动
            <span class="sy-badge">{{ hasChildren ? '已激活' : '未激活' }}</span>
          </p>
          <p class="sy-desc">有孩子档案时，相关回答自动附加「儿童-宠物互动安全」提醒</p>
        </div>
      </section>

      <!-- ===== 保存 ===== -->
      <div class="form-actions">
        <el-button type="primary" size="large" class="save-btn" :loading="saving" @click="save">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" /></svg>
          保存
        </el-button>
        <p class="mvp-note caption">当前仅支持猫 / 狗</p>
      </div>
    </el-form>

    <!-- AI 免责条 -->
    <p class="ai-note caption">
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.6" /><path d="M12 11v5M12 7.8v.4" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
      AI 生成内容，仅供参考，不替代医生诊断
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getPets, getChildren, createPet, updatePet } from '@/api/client'
import { ApiError } from '@/api/request'
import SkeletonBlock from '@/components/SkeletonBlock.vue'

const route = useRoute()
const router = useRouter()

/** 编辑态 uid */
const editUid = computed(() => (route.params.uid as string) || '')
/** 是否编辑态 */
const isEdit = computed(() => !!editUid.value)

/** 表单数据（字段契约：pet_type/breed/age_band/neutered_flag/weight_kg/main_food） */
const form = ref<any>({
  species: '',
  breed: '',
  sterilized: null,
  weight_kg: undefined as number | string | undefined,
  food: '',
  version: 0
})

/** 校验错误 */
const errs = ref<Record<string, string>>({})
/** 提交中 */
const saving = ref(false)
/** 加载态 */
const loading = ref(isEdit.value)
/** 是否已有孩子档案（协同联动卡激活条件） */
const hasChildren = ref(false)
/** 年龄下拉选中值（岁；0.5=1 岁以下，7=6 岁以上） */
const ageSel = ref<number | null>(null)

/** 猫品种候选 */
const CAT_BREEDS = ['英国短毛猫', '美国短毛猫', '布偶猫', '暹罗猫', '中华田园猫', '缅因猫', '波斯猫', '橘猫']
/** 狗品种候选 */
const DOG_BREEDS = ['金毛寻回犬', '拉布拉多', '柯基', '边境牧羊犬', '柴犬', '泰迪贵宾', '比熊', '中华田园犬']
/** 年龄下拉选项（v 为近似岁数，提交时换算 birthdate） */
const AGE_OPTIONS = [
  { v: 0.5, label: '1 岁以下（幼年期）' },
  { v: 2, label: '2 岁' },
  { v: 3, label: '3 岁' },
  { v: 4, label: '4 岁' },
  { v: 5, label: '5 岁' },
  { v: 7, label: '6 岁以上' }
]
/** 主要食物候选 */
const FOODS = ['干粮', '湿粮 / 罐头', '冻干生骨肉', '自制熟自制', '混合喂养']

/** 联动品种候选 */
const breedOptions = computed(() => (form.value.species === 'cat' ? CAT_BREEDS : DOG_BREEDS))

/** 主要食物选项（编辑态存量自由文本并入首位，避免丢失） */
const foodOptions = computed(() => {
  const f = String(form.value.food || '')
  return f && !FOODS.includes(f) ? [f, ...FOODS] : FOODS
})

/** 标准体态刻度参考（按物种给常见区间） */
const weightRef = computed(() => (form.value.species === 'dog' ? '5.0 - 30.0 kg' : '3.5 - 5.5 kg'))

/** 档案信息完备度百分比（类型/品种/年龄/绝育/体重/食物 六项） */
const completenessPct = computed(() => {
  const f = form.value
  const filled = [
    !!f.species,
    !!f.breed,
    ageSel.value !== null,
    f.sterilized !== null,
    f.weight_kg !== undefined && f.weight_kg !== '',
    !!f.food
  ].filter(Boolean).length
  return Math.round((filled / 6) * 100)
})

/**
 * 年龄选项值 → 后端 age_band
 * @param sel 年龄下拉选中值（岁）
 * @returns junior(<1y) / adult(1-7y) / senior(>7y)
 */
function ageBandOf(sel: number | null): 'junior' | 'adult' | 'senior' {
  if (sel === null || sel <= 1) return 'junior'
  if (sel >= 7) return 'senior'
  return 'adult'
}

/**
 * 后端 age_band → 年龄下拉选中值（编辑态反推）
 * @param band junior / adult / senior
 * @returns 年龄选项 v（未知返回 null）
 */
function selOfAgeBand(band: string): number | null {
  if (band === 'junior') return 0.5
  if (band === 'senior') return 7
  if (band === 'adult') return 3
  return null
}

/**
 * 物种切换：清空已选品种（保留原联动逻辑）
 * @param sp 物种 cat | dog
 */
function switchSpecies(sp: string): void {
  if (form.value.species !== sp) {
    form.value.species = sp
    form.value.breed = ''
  }
}

onMounted(async () => {
  // 协同联动条件：是否存在孩子档案（失败静默）
  try {
    const cl: any = await getChildren()
    const items = cl?.children || cl?.items || (Array.isArray(cl) ? cl : [])
    hasChildren.value = items.length > 0
  } catch {
    hasChildren.value = false
  }
  if (!isEdit.value) return
  try {
    const list: any = await getPets()
    const items = list?.pets || list?.items || (Array.isArray(list) ? list : [])
    const hit = items.find((x: any) => x.uid === editUid.value)
    if (hit) {
      // 后端字段 → 表单字段映射：pet_type/neutered_flag/main_food；年龄由 age_band 反推
      form.value = {
        ...form.value,
        species: hit.pet_type || '',
        breed: hit.breed || '',
        sterilized: hit.neutered_flag ?? null,
        weight_kg: hit.weight_kg ?? undefined,
        food: hit.main_food || '',
        version: hit.version ?? 0
      }
      ageSel.value = selOfAgeBand(hit.age_band)
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
 * 表单校验
 * @returns 是否通过
 */
function validate(): boolean {
  errs.value = {}
  if (!form.value.species) errs.value.species = '请选择类型'
  if (ageSel.value === null) errs.value.age = '请选择年龄'
  return Object.keys(errs.value).length === 0
}

/**
 * 保存（编辑走乐观锁 PUT）
 * @throws ApiError 1003 乐观锁冲突时提示重新编辑
 */
async function save(): Promise<void> {
  if (!validate()) {
    document.querySelector('.el-form-item')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return
  }
  saving.value = true
  try {
    const payload = {
      pet_type: form.value.species,
      breed: form.value.breed || 'unknown',
      age_band: ageBandOf(ageSel.value),
      neutered_flag: form.value.sterilized,
      weight_kg:
        form.value.weight_kg === '' || form.value.weight_kg === undefined
          ? undefined
          : Number(form.value.weight_kg),
      main_food: form.value.food || undefined
    }
    if (isEdit.value) {
      await updatePet(editUid.value, { ...payload, version: form.value.version })
    } else {
      await createPet(payload)
    }
    ElMessage.success('已保存')
    router.replace('/app/profiles')
  } catch (e: any) {
    if (e instanceof ApiError && e.code === 1003) {
      ElMessage.error('档案刚被其他设备修改，请返回列表重新编辑')
    } else {
      ElMessage.error(e?.message || '保存失败')
    }
  } finally {
    saving.value = false
  }
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

/* ---------- 校准进度卡 ---------- */
.calib-card {
  padding: var(--sp-4) var(--sp-5);
  margin-bottom: var(--sp-4);

  .calib-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--sp-3);

    .calib-label {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: var(--fs-caption);
      font-weight: 600;
      color: var(--ink-1);

      .dot {
        width: 6px;
        height: 6px;
        border-radius: 1px;
        background: var(--accent);
        flex: none;
      }
    }

    .calib-pct {
      font-size: var(--fs-caption);
      color: var(--accent);
      font-weight: 600;
    }
  }

  .calib-steps {
    display: flex;
    justify-content: space-between;
    margin-top: var(--sp-2);
    color: var(--ink-3);
  }
}

/* ---------- 卡片通用 ---------- */
.form-card {
  margin-bottom: var(--sp-4);

  .card-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--sp-5);

    .st-section-head {
      font-size: var(--fs-body);

      svg {
        width: 17px;
        height: 17px;
      }
    }

    .req-mark {
      font-size: var(--fs-caption);
      color: var(--danger);
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

/* 类型双卡切换 */
.species-cards {
  display: flex;
  gap: var(--sp-3);
  width: 100%;
}

.sp-card {
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

  svg {
    width: 18px;
    height: 18px;
  }

  &.on {
    border-color: var(--accent);
    background: var(--accent-soft);
    color: var(--accent);
    font-weight: 600;
  }
}

/* 体重标签行（含标准体态参考） */
.weight-lb {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;

  .weight-ref {
    color: var(--ink-3);
  }
}

/* ---------- 协同联动卡 ---------- */
.synergy-card {
  display: flex;
  gap: var(--sp-3);
  border-radius: var(--radius-face);
  border: 1px solid var(--line);
  background: var(--sc-low);
  padding: var(--sp-4) var(--sp-5);
  margin-bottom: var(--sp-5);

  &.active {
    background: var(--accent-soft);
    border-color: var(--accent-line);
  }

  .sy-ico {
    flex: none;
    color: var(--accent);
    margin-top: 2px;

    svg {
      width: 20px;
      height: 20px;
    }
  }

  .sy-text {
    flex: 1;
    min-width: 0;
  }

  .sy-title {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    font-size: var(--fs-sub);
    font-weight: 600;
    color: var(--ink-1);

    .sy-badge {
      flex: none;
      padding: 0 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      background: var(--accent);
      color: var(--sc-lowest);

      .active & {
        background: var(--accent);
      }

      /* 未激活态灰化 */
      .synergy-card:not(.active) & {
        background: var(--surface-2);
        color: var(--ink-3);
      }
    }
  }

  .sy-desc {
    margin-top: 2px;
    font-size: var(--fs-caption);
    color: var(--ink-3);
    line-height: 1.6;
  }
}

/* 保存区 */
.form-actions {
  .save-btn {
    width: 100%;
    height: 48px;
    font-size: var(--fs-body);

    svg {
      width: 16px;
      height: 16px;
      margin-right: 4px;
    }
  }

  .mvp-note {
    text-align: center;
    margin-top: var(--sp-3);
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
