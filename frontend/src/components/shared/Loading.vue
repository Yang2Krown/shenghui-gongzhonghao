<template>
  <div class="loading-container animate-fade-in">
    <svg class="spin" width="30" height="30" viewBox="0 0 24 24" fill="none" stroke="var(--clay)" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
      <path d="M20 11a8 8 0 0 0-14-4.5L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4.5L20 15M20 20v-5h-5"/>
    </svg>
    <p class="loading-text">{{ text }}</p>
  </div>
</template>

<script setup>
defineProps({
  text: { type: String, default: '正在生成…' },
})
</script>

<style scoped>
.loading-container {
  text-align: center;
  padding: 56px 0;
}

.spin {
  animation: spin 1s linear infinite;
  margin: 0 auto;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.loading-text {
  font-size: 14px;
  color: var(--ink-3);
  margin-top: 14px;
}

.animate-fade-in {
  animation: fadeIn 0.28s cubic-bezier(0.32, 0.72, 0, 1);
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
</style>
