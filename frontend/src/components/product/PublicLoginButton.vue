<template>
  <button class="btn btn-ghost public-login-button" @click="handleClick">
    {{ userStore.isAuthenticated ? '退出登录' : '登录 / 注册' }}
  </button>
</template>

<script setup>
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'

const emit = defineEmits(['authenticated'])
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const handleClick = () => {
  if (userStore.isAuthenticated) {
    userStore.logout()
    return
  }

  const query = { show: 'login' }
  if (route.name !== 'Landing') query.redirect = route.fullPath
  router.push({ name: 'Landing', query })
}
</script>

<style scoped>
.public-login-button {
  white-space: nowrap;
}
</style>
