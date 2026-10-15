export function hasAssessmentAnswer(answers: Record<number, number>, questionNo: number): boolean {
  // 用索引访问判定而非 hasOwnProperty：Vue 3.4 的 reactive 不为 hasOwnProperty 收集依赖，
  // 导致「下一题」可用态与进度 computed 在写入答案后不会重算；索引访问走 get trap 可被追踪。
  // score 恒为数字（含 0 分），与 hasOwnProperty 语义等价。
  return answers[questionNo] !== undefined
}
