export function userFacingMessage(error: unknown, fallback: string) {
  const message = error instanceof Error
    ? error.message.trim()
    : typeof error === 'string'
      ? error.trim()
      : ''

  return message && !/[A-Za-z]/.test(message) ? message : fallback
}
