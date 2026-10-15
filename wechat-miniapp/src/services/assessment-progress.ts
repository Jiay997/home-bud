const STORAGE_KEY = 'jiaban_assessment_progress'

export interface AssessmentProgress {
  assessment_uid: string
  answered: number
  total: number
  updated_at: number
}

type Storage = {
  getStorageSync(key: string): unknown
  setStorageSync(key: string, value: unknown): void
}

// 断点本地镜像，按 userUid 隔离；服务端 start 仍为断点权威来源，镜像用于首页 hero 三态与作答页即时回写
export function createAssessmentProgressStore({ storage }: { storage: Storage }) {
  function readAll(): Record<string, AssessmentProgress> {
    const raw = storage.getStorageSync(STORAGE_KEY)
    if (!raw || typeof raw !== 'object') return {}
    return raw as Record<string, AssessmentProgress>
  }

  return {
    read(userUid: string): AssessmentProgress | null {
      const row = readAll()[userUid]
      if (!row || !row.assessment_uid) return null
      return {
        assessment_uid: row.assessment_uid,
        answered: Number(row.answered) || 0,
        total: Number(row.total) || 0,
        updated_at: Number(row.updated_at) || 0
      }
    },
    write(userUid: string, progress: AssessmentProgress) {
      storage.setStorageSync(STORAGE_KEY, { ...readAll(), [userUid]: progress })
    },
    clear(userUid: string) {
      const all = readAll()
      if (!(userUid in all)) return
      delete all[userUid]
      storage.setStorageSync(STORAGE_KEY, all)
    }
  }
}
