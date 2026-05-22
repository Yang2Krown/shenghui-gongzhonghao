<template>
  <div class="register-page min-h-screen bg-ivory flex flex-col justify-center py-12 sm:px-6 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-md">
      <h2 class="mt-6 text-center text-h1 font-serif text-ink">
        注册新账号
      </h2>
      <p class="mt-2 text-center text-sm text-ink-3">
        已有账号？
        <router-link to="/login" class="font-medium text-clay-deep hover:text-clay">
          立即登录
        </router-link>
      </p>
    </div>

    <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
      <div class="card py-8 px-4 sm:px-10">
        <form class="space-y-6" @submit.prevent="handleRegister">
          <div>
            <label for="name" class="block text-sm font-medium text-ink-2">
              用户名
            </label>
            <div class="mt-1">
              <el-input
                id="name"
                v-model="form.name"
                type="text"
                placeholder="请输入用户名"
                :class="{ 'is-error': errors.name }"
                @blur="validateName"
              />
              <p v-if="errors.name" class="mt-1 text-sm text-crimson">{{ errors.name }}</p>
            </div>
          </div>

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

          <div>
            <label for="confirmPassword" class="block text-sm font-medium text-ink-2">
              确认密码
            </label>
            <div class="mt-1">
              <el-input
                id="confirmPassword"
                v-model="form.confirmPassword"
                type="password"
                placeholder="请再次输入密码"
                show-password
                :class="{ 'is-error': errors.confirmPassword }"
                @blur="validateConfirmPassword"
              />
              <p v-if="errors.confirmPassword" class="mt-1 text-sm text-crimson">{{ errors.confirmPassword }}</p>
            </div>
          </div>

          <div class="flex items-center">
            <el-checkbox v-model="form.agreeTerms">
              我已阅读并同意
              <a href="#" class="text-clay-deep hover:text-clay">服务条款</a>
              和
              <a href="#" class="text-clay-deep hover:text-clay">隐私政策</a>
            </el-checkbox>
          </div>

          <div>
            <el-button
              type="primary"
              native-type="submit"
              class="w-full"
              :loading="loading"
              :disabled="!isFormValid"
            >
              注册
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
              <el-button class="w-full" @click="handleWechatRegister">
                <el-icon><ChatDotRound /></el-icon>
                微信注册
              </el-button>
            </div>

            <div>
              <el-button class="w-full" @click="handleGithubRegister">
                <el-icon><Link /></el-icon>
                GitHub注册
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
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import { ChatDotRound, Link } from '@element-plus/icons-vue'

const router = useRouter()
const userStore = useUserStore()

// 表单数据
const form = reactive({
  name: '',
  email: '',
  password: '',
  confirmPassword: '',
  agreeTerms: false
})

// 错误信息
const errors = reactive({
  name: '',
  email: '',
  password: '',
  confirmPassword: ''
})

// 状态
const loading = ref(false)

// 计算属性
const isFormValid = computed(() => {
  return (
    form.name &&
    form.email &&
    form.password &&
    form.confirmPassword &&
    form.agreeTerms &&
    !errors.name &&
    !errors.email &&
    !errors.password &&
    !errors.confirmPassword
  )
})

// 验证用户名
const validateName = () => {
  if (!form.name) {
    errors.name = '请输入用户名'
    return false
  }
  
  if (form.name.length < 2) {
    errors.name = '用户名长度不能少于2位'
    return false
  }
  
  if (form.name.length > 20) {
    errors.name = '用户名长度不能超过20位'
    return false
  }
  
  errors.name = ''
  return true
}

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
  
  if (form.password.length > 20) {
    errors.password = '密码长度不能超过20位'
    return false
  }
  
  errors.password = ''
  return true
}

// 验证确认密码
const validateConfirmPassword = () => {
  if (!form.confirmPassword) {
    errors.confirmPassword = '请再次输入密码'
    return false
  }
  
  if (form.password !== form.confirmPassword) {
    errors.confirmPassword = '两次输入的密码不一致'
    return false
  }
  
  errors.confirmPassword = ''
  return true
}

// 验证表单
const validateForm = () => {
  const nameValid = validateName()
  const emailValid = validateEmail()
  const passwordValid = validatePassword()
  const confirmPasswordValid = validateConfirmPassword()
  return nameValid && emailValid && passwordValid && confirmPasswordValid
}

// 处理注册
const handleRegister = async () => {
  if (!validateForm()) {
    return
  }
  
  if (!form.agreeTerms) {
    ElMessage.warning('请同意服务条款和隐私政策')
    return
  }
  
  loading.value = true
  
  try {
    await userStore.register({
      username: form.name,
      email: form.email,
      password: form.password
    })
    
    // 跳转到首页
    router.push('/')
  } catch (error) {
    console.error('Register error:', error)
  } finally {
    loading.value = false
  }
}

// 微信注册
const handleWechatRegister = () => {
  ElMessage.info('微信注册功能开发中')
}

// GitHub注册
const handleGithubRegister = () => {
  ElMessage.info('GitHub注册功能开发中')
}
</script>

<style scoped>
.register-page {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.is-error :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--el-color-danger) inset;
}
</style>