<template>
  <div class="login-page min-h-screen flex flex-col justify-center py-12 sm:px-6 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-md">
      <h2 class="text-center text-h2 font-serif text-ink">
        欢迎回来
      </h2>
      <p class="mt-2 text-center text-sm text-ink-3">
        让专业的人，做出更专业的内容
      </p>
      <p class="mt-4 text-center text-sm text-ink-3">
        还没有账号？
        <router-link to="/register" class="font-medium text-clay-deep hover:text-clay">
          立即注册
        </router-link>
      </p>
    </div>

    <div class="mt-8 sm:mx-auto sm:w-full sm:max-w-md">
      <div class="login-card py-8 px-4 sm:px-10">
        <!-- 手机验证码登录 -->
        <form class="space-y-6" @submit.prevent="handlePhoneLogin">
          <div>
            <label for="email" class="block text-sm font-medium text-ink-2">
              邮箱地址
            </label>
            <div class="mt-1">
              <el-input
                v-model="phoneForm.phone"
                size="large"
                placeholder="请输入手机号"
                :class="{ 'is-error': phoneErrors.phone }"
                @blur="validatePhone"
              />
              <p v-if="phoneErrors.phone" class="mt-1 text-sm text-crimson">{{ phoneErrors.phone }}</p>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-ink-2">验证码</label>
            <div class="mt-1 flex items-stretch gap-2">
              <el-input
                v-model="phoneForm.code"
                size="large"
                placeholder="6位验证码"
                maxlength="6"
                class="flex-1"
                :class="{ 'is-error': phoneErrors.code }"
              />
              <el-button
                size="large"
                :disabled="cooldown > 0 || !phoneForm.phone"
                :loading="sendingCode"
                class="code-btn"
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
              size="large"
              native-type="submit"
              class="w-full"
              :loading="loading"
              :disabled="!phoneForm.phone || !phoneForm.code"
            >
              登录 / 注册
            </el-button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { sendSmsCode, loginByPhone } from '@/api/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const loading = ref(false)
const sendingCode = ref(false)
const cooldown = ref(0)
let cooldownTimer = null

// 手机登录表单
const phoneForm = reactive({ phone: '', code: '' })
const phoneErrors = reactive({ phone: '', code: '' })

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
    await userStore.login({
      email: form.email,
      password: form.password
    })
    
    // 跳转到之前的页面或首页
    const redirect = route.query.redirect || '/'
    router.push(redirect)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 暖色纸面背景 + 微妙的 Clay 径向光晕，对齐设计规范"像一封工作信" */
.login-page {
  background-color: var(--ivory);
  background-image:
    radial-gradient(circle at 15% 20%, rgba(204, 120, 92, 0.08), transparent 45%),
    radial-gradient(circle at 85% 80%, rgba(63, 92, 82, 0.06), transparent 50%);
}

/* 登录卡片 —— 更纸面、更克制的阴影 */
.login-card {
  background: var(--paper);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  box-shadow: var(--sh-2);
}

/* 验证码输入框与按钮严格等高（44px） */
.login-card :deep(.el-input--large) {
  --el-input-height: 44px;
}
.login-card :deep(.el-input--large .el-input__wrapper) {
  height: 44px;
  box-sizing: border-box;
  border-radius: var(--r-md) !important;
}
.login-card :deep(.el-input--large .el-input__inner) {
  height: 44px;
  line-height: 44px;
}
.login-card :deep(.code-btn.el-button) {
  height: 44px;
  min-height: 44px;
  padding: 0 18px;
  min-width: 116px;
  white-space: nowrap;
  flex-shrink: 0;
  box-sizing: border-box;
  line-height: 1;
  border-radius: var(--r-md) !important;
}

/* 错误态边框 */
.is-error :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--crimson) inset !important;
}
</style>
