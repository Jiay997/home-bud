<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { api, type ChildPayload, type ChildProfileView, type PetPayload, type PetProfileView } from '../api'
import MiniDialog from './MiniDialog.vue'
import { useDialog } from '../services/dialog'
import { userFacingMessage } from '../services/user-message'

const props = defineProps<{
  visible: boolean
  kind: 'child' | 'pet'
  profile: ChildProfileView | PetProfileView | null
}>()
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'saved', view: ChildProfileView | PetProfileView): void
  (e: 'stale'): void
  (e: 'consent-granted'): void
}>()

// 静态文案（含拉丁字母一律经 script 常量插值，模板禁止裸写）
const closeCopy = '关闭'
const cancelCopy = '取消'
const saveCopy = '保存'
const savingCopy = '正在保存…'
const updatedCopy = '档案已更新'
const createdCopy = '档案已建立'
const consentRecordedCopy = '已记录同意'
const consentFailedCopy = '同意保存失败，请稍后重试。'
const consentModalTitle = '先完成儿童信息同意'
const consentModalCopy = '建立孩子档案前，需要单独同意儿童信息处理。'
const consentModalConfirm = '去同意'
const growSectionCopy = '生长情况（选填，越全越贴合）'
const encryptNote = '儿童信息加密保存；出生日期默认脱敏展示。'
const petSafetyNote = '家里有孩子档案时，相关回答会自动附加儿童与宠物互动安全提醒。'

const genderOptions: { label: string; value: 'male' | 'female' | 'unknown' }[] = [
  { label: '男孩', value: 'male' },
  { label: '女孩', value: 'female' },
  { label: '暂不填写', value: 'unknown' }
]
const petTypeOptions: { label: string; value: 'cat' | 'dog' }[] = [
  { label: '猫', value: 'cat' },
  { label: '狗', value: 'dog' }
]
const petAgeOptions: { label: string; value: 'junior' | 'adult' | 'senior' }[] = [
  { label: '幼年', value: 'junior' },
  { label: '成年', value: 'adult' },
  { label: '老年', value: 'senior' }
]
const neuterOptions: { label: string; value: '' | 'yes' | 'no' }[] = [
  { label: '已绝育', value: 'yes' },
  { label: '未绝育', value: 'no' },
  { label: '不填写', value: '' }
]

const sheetBusy = ref(false)
const sheetError = ref('')

const childForm = reactive({
  nickname: '',
  birthDate: '',
  gender: 'unknown' as 'male' | 'female' | 'unknown',
  height: '',
  weight: '',
  allergyText: '',
  solidFood: '',
  premature: false
})
const petForm = reactive({
  petType: 'cat' as 'cat' | 'dog',
  breed: '',
  ageBand: 'adult' as 'junior' | 'adult' | 'senior',
  neutered: '' as '' | 'yes' | 'no',
  weight: '',
  mainFood: ''
})

const now = new Date()
const todayText = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`

const editing = computed(() => props.profile !== null)
const sheetTitle = computed(() => {
  const action = editing.value ? '编辑' : '新建'
  return `${action}${props.kind === 'child' ? '孩子档案' : '宠物档案'}`
})
const sheetValid = computed(() => {
  if (props.kind === 'child') return Boolean(childForm.nickname.trim() && childForm.birthDate)
  return true
})

const { dialog, openDialog, onDialogConfirm, onDialogCancel } = useDialog()

function resetChildForm() {
  Object.assign(childForm, { nickname: '', birthDate: '', gender: 'unknown', height: '', weight: '', allergyText: '', solidFood: '', premature: false })
}
function resetPetForm() {
  Object.assign(petForm, { petType: 'cat', breed: '', ageBand: 'adult', neutered: '', weight: '', mainFood: '' })
}
function fillChildForm(child: ChildProfileView) {
  Object.assign(childForm, {
    nickname: child.nickname,
    birthDate: child.birth_date,
    gender: child.gender || 'unknown',
    height: child.height_cm !== null ? String(child.height_cm) : '',
    weight: child.weight_kg !== null ? String(child.weight_kg) : '',
    allergyText: child.allergy.join('、'),
    solidFood: child.solid_food_month !== null ? String(child.solid_food_month) : '',
    premature: child.premature_flag
  })
}
function fillPetForm(pet: PetProfileView) {
  Object.assign(petForm, {
    petType: pet.pet_type,
    breed: pet.breed || '',
    ageBand: pet.age_band,
    neutered: pet.neutered_flag === true ? 'yes' : pet.neutered_flag === false ? 'no' : '',
    weight: pet.weight_kg !== null ? String(pet.weight_kg) : '',
    mainFood: pet.main_food || ''
  })
}

watch(() => props.visible, (value) => {
  if (!value) return
  sheetError.value = ''
  if (props.kind === 'child') {
    if (props.profile) fillChildForm(props.profile as ChildProfileView)
    else resetChildForm()
  } else if (props.profile) {
    fillPetForm(props.profile as PetProfileView)
  } else {
    resetPetForm()
  }
})

function close() {
  emit('close')
  sheetBusy.value = false
  sheetError.value = ''
}

function onBirthChange(event: { detail: { value: string } }) {
  childForm.birthDate = event.detail.value
}

function parseAllergy(text: string) {
  return text
    .split(/[、,，;；\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function formatNumberInput(value: string, min: number, max: number, integer = false) {
  if (!value) return undefined
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed < min || parsed > max) return undefined
  return integer ? Math.round(parsed) : parsed
}

function isChildConsentError(error: unknown) {
  return typeof (error as { code?: unknown })?.code === 'number' && (error as { code: number }).code === 1302
}
function isOptimisticLockError(error: unknown) {
  return typeof (error as { code?: unknown })?.code === 'number' && (error as { code: number }).code === 1003
}

async function agreeChildConsent() {
  try {
    await api.agreeChildConsent()
    uni.showToast({ title: consentRecordedCopy, icon: 'none' })
    emit('consent-granted')
  } catch (error: any) {
    uni.showToast({ title: userFacingMessage(error, consentFailedCopy), icon: 'none' })
  }
}

async function askConsent() {
  const result = await openDialog({
    title: consentModalTitle,
    message: consentModalCopy,
    confirmText: consentModalConfirm
  })
  if (result.confirm) void agreeChildConsent()
}

async function submit() {
  if (!sheetValid.value || sheetBusy.value) return
  sheetBusy.value = true
  sheetError.value = ''
  try {
    let saved: ChildProfileView | PetProfileView
    if (props.kind === 'child') {
      const payload: ChildPayload = { nickname: childForm.nickname.trim(), birth_date: childForm.birthDate }
      if (childForm.gender) payload.gender = childForm.gender
      const height = formatNumberInput(childForm.height, 20, 200)
      if (height !== undefined) payload.height_cm = height
      const weight = formatNumberInput(childForm.weight, 1, 100)
      if (weight !== undefined) payload.weight_kg = weight
      payload.premature_flag = childForm.premature
      const allergy = parseAllergy(childForm.allergyText)
      if (allergy.length) payload.allergy = allergy
      else if (editing.value) payload.allergy = []
      const solidFood = formatNumberInput(childForm.solidFood, 0, 36, true)
      if (solidFood !== undefined) payload.solid_food_month = solidFood
      if (editing.value && props.profile) {
        saved = await api.updateChild((props.profile as ChildProfileView).profile_uid, { ...payload, version: props.profile.version })
        uni.showToast({ title: updatedCopy, icon: 'none' })
      } else {
        saved = await api.createChild(payload)
        uni.showToast({ title: createdCopy, icon: 'none' })
      }
    } else {
      const payload: PetPayload = {
        pet_type: petForm.petType,
        age_band: petForm.ageBand,
        breed: petForm.breed.trim() || null,
        neutered_flag: petForm.neutered === 'yes' ? true : petForm.neutered === 'no' ? false : null,
        weight_kg: formatNumberInput(petForm.weight, 0.1, 100) ?? null,
        main_food: petForm.mainFood.trim() || null
      }
      if (editing.value && props.profile) {
        saved = await api.updatePet((props.profile as PetProfileView).pet_uid, { ...payload, version: props.profile.version })
        uni.showToast({ title: updatedCopy, icon: 'none' })
      } else {
        saved = await api.createPet(payload)
        uni.showToast({ title: createdCopy, icon: 'none' })
      }
    }
    close()
    emit('saved', saved)
  } catch (error: any) {
    if (isChildConsentError(error)) {
      close()
      void askConsent()
      return
    }
    if (isOptimisticLockError(error)) {
      close()
      emit('stale')
      return
    }
    sheetError.value = userFacingMessage(error, '保存失败，请稍后重试。')
  } finally {
    sheetBusy.value = false
  }
}
</script>

<template>
  <view v-if="props.visible" class="sheet-mask" @tap="close">
    <view class="sheet" @tap.stop>
      <view class="sheet-head">
        <text class="sheet-title">{{ sheetTitle }}</text>
        <button class="sheet-close" hover-class="pressed" @tap="close">{{ closeCopy }}</button>
      </view>

      <scroll-view scroll-y class="sheet-scroll">
        <template v-if="props.kind === 'child'">
          <text class="field-label">昵称 *</text>
          <input class="field-input" v-model="childForm.nickname" maxlength="32" placeholder="例如：果果" placeholder-class="field-placeholder" />
          <text class="field-label">出生日期 *</text>
          <picker mode="date" :value="childForm.birthDate" :end="todayText" @change="onBirthChange">
            <view class="field-input field-picker">
              <text :class="childForm.birthDate ? '' : 'picker-placeholder'">{{ childForm.birthDate || '选择出生日期' }}</text>
            </view>
          </picker>
          <text class="field-label">性别</text>
          <view class="chip-row">
            <button v-for="option in genderOptions" :key="option.value" class="chip" :class="{ active: childForm.gender === option.value }" hover-class="pressed" @tap="childForm.gender = option.value">{{ option.label }}</button>
          </view>
          <text class="section-caption">{{ growSectionCopy }}</text>
          <view class="field-row">
            <view class="field-half">
              <text class="field-label">身高（厘米）</text>
              <input class="field-input" type="digit" v-model="childForm.height" placeholder="选填" placeholder-class="field-placeholder" />
            </view>
            <view class="field-half">
              <text class="field-label">体重（千克）</text>
              <input class="field-input" type="digit" v-model="childForm.weight" placeholder="选填" placeholder-class="field-placeholder" />
            </view>
          </view>
          <text class="field-label">过敏项</text>
          <input class="field-input" v-model="childForm.allergyText" placeholder="选填，用顿号或逗号分隔" placeholder-class="field-placeholder" />
          <text class="field-label">辅食添加月龄</text>
          <input class="field-input" type="number" v-model="childForm.solidFood" placeholder="选填，0-36" placeholder-class="field-placeholder" />
          <view class="toggle-row" @tap="childForm.premature = !childForm.premature">
            <view class="check-mark" :class="{ checked: childForm.premature }"><view v-if="childForm.premature" class="check-tick" /></view>
            <text>早产</text>
          </view>
          <text class="encrypt-note">{{ encryptNote }}</text>
        </template>

        <template v-else>
          <text class="field-label">类型</text>
          <view class="chip-row">
            <button v-for="option in petTypeOptions" :key="option.value" class="chip" :class="{ active: petForm.petType === option.value }" hover-class="pressed" @tap="petForm.petType = option.value">{{ option.label }}</button>
          </view>
          <text class="field-label">品种</text>
          <input class="field-input" v-model="petForm.breed" maxlength="64" placeholder="选填，例如：橘猫" placeholder-class="field-placeholder" />
          <text class="field-label">年龄段</text>
          <view class="chip-row">
            <button v-for="option in petAgeOptions" :key="option.value" class="chip" :class="{ active: petForm.ageBand === option.value }" hover-class="pressed" @tap="petForm.ageBand = option.value">{{ option.label }}</button>
          </view>
          <view class="field-row">
            <view class="field-half">
              <text class="field-label">体重（千克）</text>
              <input class="field-input" type="digit" v-model="petForm.weight" placeholder="选填" placeholder-class="field-placeholder" />
            </view>
            <view class="field-half">
              <text class="field-label">主粮</text>
              <input class="field-input" v-model="petForm.mainFood" maxlength="64" placeholder="选填" placeholder-class="field-placeholder" />
            </view>
          </view>
          <text class="field-label">绝育</text>
          <view class="chip-row">
            <button v-for="option in neuterOptions" :key="option.value" class="chip" :class="{ active: petForm.neutered === option.value }" hover-class="pressed" @tap="petForm.neutered = option.value">{{ option.label }}</button>
          </view>
          <text class="encrypt-note">{{ petSafetyNote }}</text>
        </template>

        <text v-if="sheetError" class="sheet-error">{{ sheetError }}</text>
      </scroll-view>

      <view class="sheet-actions">
        <button class="primary-button" :class="{ disabled: !sheetValid || sheetBusy }" :disabled="!sheetValid || sheetBusy" hover-class="pressed" @tap="submit">{{ sheetBusy ? savingCopy : saveCopy }}</button>
        <button class="ghost-button" hover-class="pressed" @tap="close">{{ cancelCopy }}</button>
      </view>
    </view>
  </view>

  <MiniDialog
    :visible="dialog.visible"
    :title="dialog.title"
    :message="dialog.message"
    :confirm-text="dialog.confirmText"
    :cancel-text="dialog.cancelText"
    :show-cancel="dialog.showCancel"
    :danger="dialog.danger"
    :input="dialog.input"
    @confirm="onDialogConfirm"
    @cancel="onDialogCancel"
  />
</template>

<style scoped>
.pressed { opacity: .82; }
.sheet-mask { position: fixed; top: 0; right: 0; bottom: 0; left: 0; z-index: 80; background: rgba(46, 51, 46, .4); }
.sheet { position: fixed; right: 0; bottom: 0; left: 0; z-index: 90; display: flex; flex-direction: column; max-height: 88vh; padding-bottom: env(safe-area-inset-bottom); background: var(--surface); border-radius: var(--r-card) var(--r-card) 0 0; }
.sheet-head { display: flex; align-items: center; justify-content: space-between; padding: 28rpx 28rpx 16rpx; }
.sheet-title { color: var(--ink-1); font-size: 31rpx; font-weight: 650; }
.sheet-close { margin: 0; padding: 4rpx 0; color: var(--ink-3); background: transparent; border: 0; font-size: 25rpx; line-height: 1.4; }
.sheet-scroll { height: 56vh; padding: 0 28rpx; box-sizing: border-box; }
.field-label { display: block; margin-top: 22rpx; color: var(--ink-2); font-size: 25rpx; }
.section-caption { display: block; margin-top: 26rpx; color: var(--ink-3); font-size: 23rpx; }
.field-input { width: 100%; height: 84rpx; line-height: 84rpx; margin-top: 10rpx; padding: 0 22rpx; box-sizing: border-box; color: var(--ink-1); background: var(--surface-warm); border: 1px solid var(--line); border-radius: var(--r-inner); font-size: 27rpx; }
.field-picker { display: flex; align-items: center; }
.picker-placeholder { color: var(--ink-3); }
.field-placeholder { color: var(--ink-3); }
.field-row { display: flex; gap: 18rpx; }
.field-half { flex: 1; min-width: 0; }
.chip-row { display: flex; flex-wrap: wrap; gap: 12rpx; margin-top: 12rpx; }
.chip { flex: none; display: inline-flex; align-items: center; justify-content: center; min-height: 66rpx; margin: 0; padding: 0 26rpx; color: var(--ink-2); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-control); font-size: 24rpx; line-height: 1; }
.chip.active { color: var(--primary-press); background: var(--primary-soft); border-color: var(--primary); }
.toggle-row { display: flex; align-items: center; gap: 14rpx; margin: 24rpx 0 8rpx; color: var(--ink-1); font-size: 25rpx; }
.check-mark { display: flex; align-items: center; justify-content: center; width: 36rpx; height: 36rpx; flex: none; color: var(--on-primary); border: 2rpx solid var(--line); border-radius: 8rpx; font-size: 24rpx; }
.check-mark.checked { background: var(--primary); border-color: var(--primary); }
.check-tick { width: 16rpx; height: 9rpx; border-left: 3rpx solid var(--on-primary); border-bottom: 3rpx solid var(--on-primary); transform: rotate(-45deg) translateY(-2rpx); }
.encrypt-note { display: block; margin: 20rpx 0 10rpx; color: var(--ink-3); font-size: 22rpx; line-height: 1.55; }
.sheet-error { display: block; margin: 18rpx 0 8rpx; color: var(--danger); font-size: 23rpx; line-height: 1.5; }
.sheet-actions { display: flex; gap: 18rpx; padding: 20rpx 28rpx 26rpx; border-top: 1px solid var(--line); }
.primary-button { display: flex; flex: 1; align-items: center; justify-content: center; min-height: 88rpx; margin: 0; color: var(--on-primary); background: var(--primary); border: 0; border-radius: var(--r-control); font-size: 28rpx; font-weight: 650; }
.primary-button.disabled { opacity: .55; }
.ghost-button { flex: none; width: 180rpx; min-height: 88rpx; margin: 0; color: var(--ink-2); background: transparent; border: 1px solid var(--line); border-radius: var(--r-control); font-size: 26rpx; }

@media (prefers-reduced-motion: reduce) {
  .chip { transition: none; }
}
</style>
