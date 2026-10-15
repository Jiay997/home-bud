/**
 * 用户 Store
 * 职责：token / 用户信息 / 额度 / 当前问答对象档案的集中管理；
 * token 与 device_id 持久化到 localStorage。
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { devLogin, getQuota, getMe } from '@/api/client'
import {
  getToken,
  setToken,
  clearToken,
  newRequestId
} from '@/api/request'

/** DEVICE_ID 在 localStorage 的键名 */
const DEVICE_KEY = 'jiaban_device_id'
/** 当前问答对象 uid 键名 */
const CURRENT_PROFILE_KEY = 'jiaban_current_profile'

/**
 * 读取或首次生成持久化设备 id
 * @returns uuid 字符串
 */
export function getDeviceId(): string {
  let id = localStorage.getItem(DEVICE_KEY)
  if (!id) {
    id = newRequestId()
    localStorage.setItem(DEVICE_KEY, id)
  }
  return id
}

export const useUserStore = defineStore('user', () => {
  /** 访问令牌 */
  const token = ref<string | null>(getToken())
  /** 用户 uid */
  const userUid = ref<string>('')
  /** 会员状态（free/active 等） */
  const memberStatus = ref<string>('free')
  /** 当日额度使用数 */
  const quotaUsed = ref(0)
  /** 当日额度上限 */
  const quotaLimit = ref(5)
  /** 剩余额度 */
  const quotaRemaining = ref(5)
  /** 会员不限次（后端 quota.unlimited；此时 limit/remaining 为 null） */
  const quotaUnlimited = ref(false)
  /** 当前问答对象档案 uid（孩子或宠物） */
  const currentProfileUid = ref<string | null>(
    localStorage.getItem(CURRENT_PROFILE_KEY)
  )

  /** 会员态是否已从服务端初始化 */
  const memberInited = ref(false)
  /** 是否已登录（有 token 即视为登录） */
  const isLoggedIn = computed(() => !!token.value)
  /** 是否会员（后端口径：free / member 或 active 均兼容） */
  const isMember = computed(
    () =>
      memberStatus.value === 'active' ||
      memberStatus.value === 'member' ||
      quotaLimit.value > 5
  )

  /**
   * 设备登录（幂等：已有 token 则跳过）
   * @throws 登录接口失败时抛 ApiError
   */
  async function login(): Promise<void> {
    if (token.value) return
    const res = await devLogin(getDeviceId())
    token.value = res.access_token
    userUid.value = res.user_uid
    memberStatus.value = res.member_status
    memberInited.value = true
    setToken(res.access_token)
  }

  /**
   * 手动写入 token（dev 场景）
   * @param t 访问令牌
   */
  function setAccessToken(t: string): void {
    token.value = t
    setToken(t)
  }

  /**
   * 刷新额度
   * @throws 接口失败时抛 ApiError（调用方可静默处理）
   */
  async function refreshQuota(): Promise<void> {
    try {
      const q = await getQuota()
      quotaUsed.value = q.used ?? 0
      quotaUnlimited.value = q.unlimited === true
      // 会员 limit/remaining 为 null：保留上一次数值（避免页面出现 "1/null"）
      if (typeof q.limit === 'number') quotaLimit.value = q.limit
      if (typeof q.remaining === 'number') quotaRemaining.value = q.remaining
    } catch {
      // 静默失败：首页已有骨架/失败兜底
    }
  }

  /**
   * 拉取用户信息
   */
  async function refreshMe(): Promise<void> {
    try {
      const me: any = await getMe()
      if (me?.member_status) memberStatus.value = me.member_status
      if (me?.user_uid) userUid.value = me.user_uid
      memberInited.value = true
    } catch {
      // 静默
    }
  }

  /**
   * 设置当前问答对象并持久化
   * @param uid 档案 uid
   */
  function setCurrentProfile(uid: string | null): void {
    currentProfileUid.value = uid
    if (uid) localStorage.setItem(CURRENT_PROFILE_KEY, uid)
    else localStorage.removeItem(CURRENT_PROFILE_KEY)
  }

  /**
   * 登出：清 token 与本地态
   */
  function logout(): void {
    clearToken()
    token.value = null
    userUid.value = ''
  }

  return {
    token,
    userUid,
    memberStatus,
    memberInited,
    quotaUsed,
    quotaLimit,
    quotaRemaining,
    quotaUnlimited,
    currentProfileUid,
    isLoggedIn,
    isMember,
    login,
    setAccessToken,
    refreshQuota,
    refreshMe,
    setCurrentProfile,
    logout
  }
})
