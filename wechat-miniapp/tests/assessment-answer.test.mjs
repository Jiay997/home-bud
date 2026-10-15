import test from 'node:test'
import assert from 'node:assert/strict'
import { hasAssessmentAnswer } from '../src/services/assessment-answer.ts'

test('a saved zero score is still a completed assessment answer', () => {
  assert.equal(hasAssessmentAnswer({ 3: 0 }, 3), true)
})

test('an answer is incomplete only when its question number is absent', () => {
  assert.equal(hasAssessmentAnswer({}, 3), false)
})
