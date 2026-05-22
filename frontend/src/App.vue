<template>
  <router-view />
</template>

<script setup>
import { onMounted } from 'vue'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

onMounted(() => {
  // 初始化时检查用户登录状态
  userStore.initialize()
})
</script>

<style>
/* 全局样式 */
html, body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: var(--sans);
  background: var(--ivory);
  color: var(--ink);
}

#app {
  height: 100%;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--bone);
  border-radius: var(--r-xs);
}

::-webkit-scrollbar-thumb {
  background: var(--line);
  border-radius: var(--r-xs);
}

::-webkit-scrollbar-thumb:hover {
  background: var(--ink-4);
}
</style>