<template>
  <svg :width="size" :height="size" :viewBox="`0 0 ${size} ${size}`" class="radar-svg">
    <!-- Grid levels -->
    <path
      v-for="level in levels"
      :key="level"
      :d="gridPath(level)"
      fill="none"
      stroke="var(--line, #e5e5e5)"
      stroke-width="1"
    />
    <!-- Axis lines -->
    <line
      v-for="(_, i) in keys"
      :key="'axis-' + i"
      :x1="cx"
      :y1="cy"
      :x2="point(i, R).x"
      :y2="point(i, R).y"
      stroke="var(--line, #e5e5e5)"
      stroke-width="1"
    />
    <!-- Data polygon -->
    <template v-if="radar">
      <path
        :d="dataPath()"
        fill="rgba(204,120,92,0.15)"
        stroke="var(--clay, #cc785c)"
        stroke-width="2"
      />
      <circle
        v-for="(_, i) in keys"
        :key="'dot-' + i"
        :cx="getPoint(i).x"
        :cy="getPoint(i).y"
        r="4"
        fill="var(--clay, #cc785c)"
      />
    </template>
    <!-- Labels -->
    <text
      v-for="(key, i) in keys"
      :key="'label-' + i"
      :x="labelOffset(i).x"
      :y="labelOffset(i).y"
      :text-anchor="labelOffset(i).anchor"
      dominant-baseline="middle"
      font-size="11"
      fill="var(--ink-2, #555)"
      font-family="var(--sans, sans-serif)"
    >
      {{ key }}
    </text>
  </svg>
</template>

<script setup>
const props = defineProps({
  radar: {
    type: Object,
    default: null,
  },
  keys: {
    type: Array,
    default: () => ['语气温度', '专业密度', '句式节奏', '情绪强度', '修辞偏好', '结构习惯'],
  },
  size: {
    type: Number,
    default: 240,
  },
})

const levels = [2, 4, 6, 8, 10]
const R = 90

const cx = props.size / 2
const cy = props.size / 2
const n = props.keys.length

const angle = (i) => (Math.PI * 2 * i) / n - Math.PI / 2

const point = (i, r) => ({
  x: cx + r * Math.cos(angle(i)),
  y: cy + r * Math.sin(angle(i)),
})

const getPoint = (i) => {
  const val = props.radar?.[props.keys[i]] ?? 5
  const r = (val / 10) * R
  return point(i, r)
}

const labelOffset = (i) => {
  const a = angle(i)
  const dx = Math.cos(a)
  const dy = Math.sin(a)
  const px = cx + (R + 22) * dx
  const py = cy + (R + 22) * dy
  let anchor = 'middle'
  if (dx > 0.3) anchor = 'start'
  else if (dx < -0.3) anchor = 'end'
  return { x: px, y: py, anchor }
}

const gridPath = (level) => {
  const r = (level / 10) * R
  return props.keys
    .map((_, i) => {
      const { x, y } = point(i, r)
      return i === 0 ? `M${x},${y}` : `L${x},${y}`
    })
    .join(' ') + 'Z'
}

const dataPath = () => {
  if (!props.radar) return ''
  return props.keys
    .map((key, i) => {
      const val = props.radar[key] ?? 5
      const r = (val / 10) * R
      const { x, y } = point(i, r)
      return i === 0 ? `M${x},${y}` : `L${x},${y}`
    })
    .join(' ') + 'Z'
}
</script>

<style scoped>
.radar-svg {
  display: block;
  margin: 0 auto;
}
</style>
