import test from 'node:test'
import assert from 'node:assert/strict'
import { needsBaseConsent } from '../src/services/consent.ts'

test('base consent is required until the current account has an active agreement', () => {
  assert.equal(needsBaseConsent({ base: { agreed: true } }), false)
  assert.equal(needsBaseConsent({ base: { agreed: false } }), true)
  assert.equal(needsBaseConsent({}), true)
})
