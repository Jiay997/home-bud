<script setup lang="ts">
withDefaults(defineProps<{
  heading: string
  example: string
  factors: string[]
  note: string
  tone?: 'child' | 'pet'
}>(), { tone: 'child' })
</script>

<template>
  <section class="scenario-guide" :class="`tone-${tone}`">
    <div class="guide-field" aria-hidden="true">
      <span class="field-line line-a" />
      <span class="field-line line-b" />
      <span class="field-tick tick-a" />
      <span class="field-tick tick-b" />
      <span class="field-tick tick-c" />
      <span class="field-origin" />
    </div>
    <div class="guide-copy">
      <h2>{{ heading }}</h2>
      <p>{{ example }}</p>
      <ul class="guide-factors" aria-label="问题观察要素">
        <li v-for="factor in factors" :key="factor">{{ factor }}</li>
      </ul>
      <p class="guide-note">{{ note }}</p>
    </div>
  </section>
</template>

<style lang="scss" scoped>
.scenario-guide {
  display: grid;
  grid-template-columns: 54px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  padding: 30px 2px 24px;

  &.tone-child { --guide-tone: var(--perspective-child); }
  &.tone-pet { --guide-tone: var(--perspective-pet); }
}

.guide-field {
  position: relative;
  width: 52px;
  height: 76px;
  margin-top: 2px;
}

.field-line {
  position: absolute;
  display: block;
  width: 1px;
  height: 62px;
  background: var(--guide-tone);
  opacity: 0.45;
  transform-origin: bottom;
}

.line-a { left: 25px; bottom: 5px; transform: rotate(32deg); }
.line-b { left: 25px; bottom: 5px; transform: rotate(-32deg); }

.field-tick,
.field-origin {
  position: absolute;
  display: block;
  border: 1px solid var(--guide-tone);
  background: var(--bg);
}

.field-tick { width: 7px; height: 7px; border-radius: 1px; }
.tick-a { left: 3px; top: 8px; }
.tick-b { right: 1px; top: 21px; }
.tick-c { left: 21px; bottom: 0; }
.field-origin { left: 20px; top: 31px; width: 12px; height: 12px; border-radius: 50%; background: var(--guide-tone); }

.guide-copy { min-width: 0; }

.guide-copy h2 {
  color: var(--ink-1);
  font-size: 19px;
  font-weight: 650;
  line-height: 1.35;
}

.guide-copy > p:not(.guide-note) {
  margin-top: 5px;
  color: var(--ink-2);
  font-size: var(--fs-sub);
  line-height: 1.55;
}

.guide-factors {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 14px;
  padding: 10px 0 0;
  margin: 10px 0 0;
  border-top: 1px solid var(--line);
  list-style: none;

  li {
    position: relative;
    padding-left: 10px;
    color: var(--ink-2);
    font-size: var(--fs-caption);
  }

  li::before {
    position: absolute;
    top: .6em;
    left: 0;
    width: 5px;
    height: 5px;
    border-radius: 1px;
    background: var(--guide-tone);
    content: '';
  }
}

.guide-note {
  margin-top: 12px;
  color: var(--ink-3);
  font-size: var(--fs-caption);
  line-height: 1.55;
}

@media (max-width: 360px) {
  .scenario-guide { grid-template-columns: 42px minmax(0, 1fr); gap: 8px; }
  .guide-field { transform: scale(.84); transform-origin: top left; }
}
</style>
