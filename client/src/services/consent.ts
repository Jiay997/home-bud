export function needsBaseConsent(status: Record<string, { agreed?: boolean }> | null | undefined) {
  return status?.base?.agreed !== true
}
