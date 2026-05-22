<template>
  <div class="login-page min-h-screen flex flex-col justify-center py-12 sm:px-6 lg:px-8">
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
        <!-- Tab 切换 -->
        <el-tabs v-model="activeTab" class="mb-6">
          <el-tab-pane label="手机验证码" name="phone" />
          <el-tab-pane label="邮箱密码" name="email" />
        </el-tabs>

        <!-- 手机验证码登录 -->
        <form v-if="activeTab === 'phone'" class="space-y-6" @submit.prevent="handlePhoneLogin">
          <div>
            <label class="block text-sm font-medium text-ink-2">手机号</label>
            <div class="mt-1">
              <el-input
                v-model="phoneForm.phone"
                placeholder="请输入手机号"
                :class="{ 'is-error': phoneErrors.phone }"
                @blur="validatePhone"
              />
              <p v-if="phoneErrors.phone" class="mt-1 text-sm text-crimson">{{ phoneErrors.phone }}</p>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-ink-2">验证码</label>
            <div class="mt-1 flex gap-2">
              <el-input
                v-model="phoneForm.code"
                placeholder="6位验证码"
                maxlength="6"
                :class="{ 'is-error': phoneErrors.code }"
              />
              <el-button
                :disabled="cooldown > 0 || !phoneForm.phone"
                :loading="sendingCode"
                style="white-space: nowrap; min-width: 110px;"
                @click="handleSendCode"
              >
                {{ cooldown > 0 ? `${cooldown}s 后重发` : '获取验证码' }}
              </el-button>
            </div>
            <p v-if="phoneErrors.code" class="mt-1 text-sm text-crimson">{{ phoneErrors.code }}</p>
          </div>

          <div>
            <el-button
              type="primary"
              native-type="submit"
              class="w-full"
              :loading="loading"
              :disabled="!phoneForm.phone || !phoneForm.code"
            >
              登录 / 注册
            </el-button>
          </div>
        </form>

        <!-- 邮箱密码登录 -->
        <form v-else class="space-y-6" @submit.prevent="handleEmailLogin">
          <div>
            <label class="block text-sm font-medium text-ink-2">邮箱地址</label>
            <div class="mt-1">
              <el-input
                v-model="emailForm.email"
                type="email"
                placeholder="请输入邮箱地址"
                :class="{ 'is-error': emailErrors.email }"
                @blur="validateEmail"
              />
              <p v-if="emailErrors.email" class="mt-1 text-sm text-crimson">{{ emailErrors.email }}</p>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-ink-2">密码</label>
            <div class="mt-1">
              <el-input
                v-model="emailForm.password"
                type="password"
                placeholder="请输入密码"
                show-password
                :class="{ 'is-error': emailErrors.password }"
                @blur="validatePassword"
              />
              <p v-if="emailErrors.password" class="mt-1 text-sm text-crimson">{{ emailErrors.password }}</p>
            </div>
          </div>

          <div class="flex items-center justify-between">
            <el-checkbox v-model="emailForm.remember">记住我</el-checkbox>
            <a href="#" class="text-sm font-medium text-clay-deep hover:text-clay">忘记密码？</a>
          </div>

          <div>
            <el-button
              type="primary"
              native-type="submit"
              class="w-full"
              :loading="loading"
              :disabled="!isEmailFormValid"
            >
              登录
            </el-button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { sendSmsCode, loginByPhone } from '@/api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const activeTab = ref('phone')
const loading = ref(false)
const sendingCode = ref(false)
const cooldown = ref(0)
let cooldownTimer = null

// 手机登录表单
const phoneForm = reactive({ phone: '', code: '' })
const phoneErrors = reactive({ phone: '', code: '' })

// 邮箱登录表单
const emailForm = reactive({ email: '', password: '', remember: false })
const emailErrors = reactive({ email: '', password: '' })

const isEmailFormValid = computed(() =>
  emailForm.email && emailForm.password && !emailErrors.email && !emailErrors.password
)

// --- 手机号验证 ---
const validatePhone = () => {
  if (!phoneForm.phone) {
    phoneErrors.phone = '请输入手机号'
    return false
  }
  if (!/^1[3-9]\d{9}$/.test(phoneForm.phone)) {
    phoneErrors.phone = '请输入有效的手机号'
    return false
  }
  phoneErrors.phone = ''
  return true
}

// --- 发送验证码 ---
const handleSendCode = async () => {
  if (!validatePhone()) return
  sendingCode.value = true
  try {
    await sendSmsCode(phoneForm.phone)
    ElMessage.success('验证码已发送，请注意查收')
    startCooldown()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '发送失败，请稍后重试')
  } finally {
    sendingCode.value = false
  }
}

const startCooldown = () => {
  cooldown.value = 60
  cooldownTimer = setInterval(() => {
    cooldown.value--
    if (cooldown.value <= 0) {
      clearInterval(cooldownTimer)
      cooldownTimer = null
    }
  }, 1000)
}

onUnmounted(() => {
  if (cooldownTimer) clearInterval(cooldownTimer)
})

// --- 手机验证码登录 ---
const handlePhoneLogin = async () => {
  if (!validatePhone()) return
  if (!phoneForm.code) {
    phoneErrors.code = '请输入验证码'
    return
  }
  phoneErrors.code = ''
  loading.value = true
  try {
    const res = await loginByPhone(phoneForm.phone, phoneForm.code)
    const { access_token, refresh_token } = res.data
    userStore.token = access_token
    userStore.refreshToken = refresh_token
    localStorage.setItem('token', access_token)
    localStorage.setItem('refreshToken', refresh_token)
    await userStore.fetchUser()
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

// --- 邮箱密码登录 ---
const validateEmail = () => {
  if (!emailForm.email) { emailErrors.email = '请输入邮箱地址'; return false }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailForm.email)) { emailErrors.email = '请输入有效的邮箱地址'; return false }
  emailErrors.email = ''
  return true
}
const validatePassword = () => {
  if (!emailForm.password) { emailErrors.password = '请输入密码'; return false }
  if (emailForm.password.length < 6) { emailErrors.password = '密码长度不能少于6位'; return false }
  emailErrors.password = ''
  return true
}

const handleEmailLogin = async () => {
  if (!validateEmail() || !validatePassword()) return
  loading.value = true
  try {
    await userStore.login({ email: emailForm.email, password: emailForm.password })
    router.push(route.query.redirect || '/')
  } catch (error) {
    console.error('Login error:', error)
  } finally {
    loading.value = false
  }
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
