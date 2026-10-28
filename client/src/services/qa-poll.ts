type QaPollOptions<T> = {
  getSession: () => Promise<T>
  getTriggerError: () => string | null
  sleep?: (milliseconds: number) => Promise<void>
  attempts?: number
  intervalMs?: number
}

export async function pollQaSession<T extends { status?: string; sections?: unknown[] }>({
  getSession,
  getTriggerError,
  sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)),
  attempts = 40,
  intervalMs = 1500
}: QaPollOptions<T>) {
  let result: T | null = null
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    result = await getSession()
    if (result.status === 'done' || (result.sections?.length || 0) > 0) break
    if (result.status === 'blocked' || result.status === 'failed') break
    const triggerError = getTriggerError()
    if (triggerError) throw new Error(triggerError)
    if (attempt + 1 < attempts) await sleep(intervalMs)
  }
  return result
}
