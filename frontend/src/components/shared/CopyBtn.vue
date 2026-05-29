<template>
  <button class="btn btn-text btn-sm" @click="copy">
    <svg v-if="!done" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/></svg>
    <svg v-else width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--clay)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>
    {{ done ? '已复制' : label }}
  </button>
</template>

<script setup>
import { ref } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  label: { type: String, default: '复制' },
})

const done = ref(false)

const copy = () => {
  navigator.clipboard?.writeText(props.text).catch(() => {})
  done.value = true
  setTimeout(() => { done.value = false }, 1400)
}
</script>
