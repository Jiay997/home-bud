const STORAGE_KEY = 'jiaban_qa_target'

export interface QaTarget {
  profile_uid: string
  name: string
}

type Storage = {
  getStorageSync(key: string): unknown
  setStorageSync(key: string, value: unknown): void
}

// 问答对象选择本地记忆：按 userUid 分桶 + 按 entry 分键，多账号共用设备时互不可见
export function createQaTargetStore({ storage }: { storage: Storage }) {
  function readAll(): Record<string, Record<string, QaTarget>> {
    const raw = storage.getStorageSync(STORAGE_KEY)
    if (!raw || typeof raw !== 'object') return {}
    return raw as Record<string, Record<string, QaTarget>>
  }

  return {
    read(entry: string, userUid: string): QaTarget | null {
      const row = readAll()[userUid]?.[entry]
      if (!row || !row.profile_uid) return null
      return { profile_uid: row.profile_uid, name: row.name || '' }
    },
    write(entry: string, userUid: string, target: QaTarget) {
      const all = readAll()
      storage.setStorageSync(STORAGE_KEY, {
        ...all,
        [userUid]: { ...(all[userUid] || {}), [entry]: { profile_uid: target.profile_uid, name: target.name } }
      })
    },
    clear(entry: string, userUid: string) {
      const all = readAll()
      const bucket = all[userUid]
      if (!bucket || !(entry in bucket)) return
      delete bucket[entry]
      storage.setStorageSync(STORAGE_KEY, all)
    }
  }
}
