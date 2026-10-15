const STORAGE_KEY = 'jiaban_current_profile'

export interface CurrentProfile {
  profile_type: 'child' | 'pet'
  profile_uid: string
}

type Storage = {
  getStorageSync(key: string): unknown
  setStorageSync(key: string, value: unknown): void
}

// 当前观察对象本地记忆：后端无单档案 GET，「当前」徽标需跨页面/重载存活
export function createProfileCurrentStore({ storage }: { storage: Storage }) {
  return {
    read(): CurrentProfile | null {
      const raw = storage.getStorageSync(STORAGE_KEY)
      if (!raw || typeof raw !== 'object') return null
      const row = raw as { profile_type?: unknown; profile_uid?: unknown }
      const profileType = row.profile_type
      const profileUid = row.profile_uid
      if (profileType !== 'child' && profileType !== 'pet') return null
      if (typeof profileUid !== 'string' || !profileUid) return null
      return { profile_type: profileType, profile_uid: profileUid }
    },
    write(value: CurrentProfile) {
      storage.setStorageSync(STORAGE_KEY, { profile_type: value.profile_type, profile_uid: value.profile_uid })
    },
    clear() {
      storage.setStorageSync(STORAGE_KEY, '')
    }
  }
}
