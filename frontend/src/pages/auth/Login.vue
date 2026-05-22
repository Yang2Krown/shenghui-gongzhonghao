<template>
  <div class="login-page min-h-screen bg-ivory flex flex-col justify-center py-12 sm:px-6 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-md">
      <h2 class="mt-6 text-center text-h1 font-serif text-ink">
        登录到 AI公众号内容运营平台
      </h2>
      <p class="mt-2 text-center text-sm text-ink-3">
        还没有账号？
        <router-link to="/register" class="font-medium text-clay-deep hover:text-clay">
          立即注册
        </router-link>
      </p>
    </div>

    <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
      <div class="card py-8 px-4 sm:px-10">
        <form class="space-y-6" @submit.prevent="handleLogin">
          <div>
            <label for="email" class="block text-sm font-medium text-ink-2">
              邮箱地址
            </label>
            <div class="mt-1">
              <el-input
                id="email"
                v-model="form.email"
                type="email"
                placeholder="请输入邮箱地址"
                :class="{ 'is-error': errors.email }"
                @blur="validateEmail"
              />
              <p v-if="errors.email" class="mt-1 text-sm text-crimson">{{ errors.email }}</p>
            </div>
          </div>

          <div>
            <label for="password" class="block text-sm font-medium text-ink-2">
              密码
            </label>
            <div class="mt-1">
              <el-input
                id="password"
                v-model="form.password"
                type="password"
                placeholder="请输入密码"
                show-password
                :class="{ 'is-error': errors.password }"
                @blur="validatePassword"
              />
              <p v-if="errors.password" class="mt-1 text-sm text-crimson">{{ errors.password }}</p>
            </div>
          </div>

          <div class="flex items-center justify-between">
            <div class="flex items-center">
              <el-checkbox v-model="form.remember">记住我</el-checkbox>
            </div>

            <div class="text-sm">
              <a href="#" class="font-medium text-clay-deep hover:text-clay">
                忘记密码？
              </a>
            </div>
          </div>

          <div>
            <el-button
              type="primary"
              native-type="submit"
              class="w-full"
              :loading="loading"
              :disabled="!isFormValid"
            >
              登录
            </el-button>
          </div>
        </form>

        <div class="mt-6">
          <div class="relative">
            <div class="absolute inset-0 flex items-center">
              <div class="w-full border-t border-line" />
            </div>
            <div class="relative flex justify-center text-sm">
              <span class="px-2 bg-paper text-ink-3">或者</span>
            </div>
          </div>

          <div class="mt-6 grid grid-cols-2 gap-3">
            <div>
              <el-button class="w-full" @click="handleWechatLogin">
                <el-icon><ChatDotRound /></el-icon>
                微信登录
              </el-button>
            </div>

            <div>
              <el-button class="w-full" @click="handleGithubLogin">
                <el-icon><Link /></el-icon>
                GitHub登录
              </el-button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Link } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 表单数据
const form = reactive({
  email: '',
  password: '',
  remember: false
})

// 错误信息
const errors = reactive({
  email: '',
  password: ''
})

// 状态
const loading = ref(false)

// 计算属性
const isFormValid = computed(() => {
  return form.email && form.password && !errors.email && !errors.password
})

// 验证邮箱
const validateEmail = () => {
  if (!form.email) {
    errors.email = '请输入邮箱地址'
    return false
  }
  
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  if (!emailRegex.test(form.email)) {
    errors.email = '请输入有效的邮箱地址'
    return false
  }
  
  errors.email = ''
  return true
}

// 验证密码
const validatePassword = () => {
  if (!form.password) {
    errors.password = '请输入密码'
    return false
  }
  
  if (form.password.length < 6) {
    errors.password = '密码长度不能少于6位'
    return false
  }
  
  errors.password = ''
  return true
}

// 验证表单
const validateForm = () => {
  const emailValid = validateEmail()
  const passwordValid = validatePassword()
  return emailValid && passwordValid
}

// 处理登录
const handleLogin = async () => {
  if (!validateForm()) {
    return
  }
  
  loading.value = true
  
  try {
    await userStore.login({
      email: form.email,
      password: form.password
    })
    
    // 跳转到之前的页面或首页
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (error) {
    console.error('Login error:', error)
  } finally {
    loading.value = false
  }
}

// 微信登录
const handleWechatLogin = () => {
  ElMessage.info('微信登录功能开发中')
}

// GitHub登录
const handleGithubLogin = () => {
  ElMessage.info('GitHub登录功能开发中')
}
</script>

<style scoped>
.login-page {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.is-error :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-color-danger) inset;
}
</style>