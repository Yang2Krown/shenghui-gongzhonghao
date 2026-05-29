<template>
  <button
    :class="['nav-item', { active, indent }]"
    @click="$emit('click')"
  >
    <component :is="iconComponent" />
    <span>{{ label }}</span>
  </button>
</template>

<script setup>
import { h, computed } from 'vue'

const props = defineProps({
  active: Boolean,
  icon: String,
  label: String,
  indent: Boolean,
})

defineEmits(['click'])

const icons = {
  Document: () => h('svg', { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
    h('path', { d: 'M14 3v5h5' }),
    h('path', { d: 'M6 3h8l5 5v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z' }),
    h('path', { d: 'M8 13h8M8 17h6' }),
  ]),
  View: () => h('svg', { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
    h('circle', { cx: 12, cy: 12, r: 3 }),
    h('path', { d: 'M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1' }),
  ]),
  List: () => h('svg', { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
    h('path', { d: 'M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01' }),
  ]),
  ChatDotSquare: () => h('svg', { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
    h('path', { d: 'M5 5h14M9 5v14M15 5v6M13 11h4' }),
  ]),
  Switch: () => h('svg', { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
    h('path', { d: 'M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7' }),
  ]),
  Edit: () => h('svg', { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
    h('path', { d: 'M14 4l6 6L9 21H3v-6L14 4z' }),
    h('path', { d: 'M12 6l6 6' }),
  ]),
  Clock: () => h('svg', { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
    h('circle', { cx: 12, cy: 12, r: 9 }),
    h('path', { d: 'M12 7v5l3 2' }),
  ]),
  User: () => h('svg', { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
    h('circle', { cx: 12, cy: 8, r: 4 }),
    h('path', { d: 'M4 20c0-3.3 3.6-6 8-6s8 2.7 8 6' }),
  ]),
  EditPen: () => h('svg', { width: 19, height: 19, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, [
    h('path', { d: 'M14.5 6a3.5 3.5 0 0 0-4.9 4.4L3 17v4h4l6.6-6.6A3.5 3.5 0 0 0 18 9.5' }),
    h('circle', { cx: 17, cy: 7, r: 0.5, fill: 'currentColor' }),
  ]),
}

const iconComponent = computed(() => icons[props.icon] || icons.Document)
</script>

<style scoped>
.nav-item {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  text-align: left;
  padding: 10px 14px;
  border: none;
  cursor: pointer;
  border-radius: var(--r-md);
  font-family: inherit;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink-2);
  background: transparent;
  transition: all 0.14s;
}

.nav-item:hover {
  color: var(--ink);
  background: var(--bone);
}

.nav-item.active {
  font-weight: 600;
  color: var(--clay-deep);
  background: var(--clay-tint);
}

.nav-item.indent {
  padding: 9px 14px 9px 40px;
}

.nav-item.indent :deep(svg) {
  width: 17px;
  height: 17px;
}
</style>
