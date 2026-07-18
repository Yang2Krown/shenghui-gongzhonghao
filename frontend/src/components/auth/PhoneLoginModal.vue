<template>
  <Teleport to="body">
    <div v-if="open" class="plm-backdrop" @click.self="close">
      <div class="plm-modal" role="dialog" aria-modal="true">
        <button class="plm-close" @click="close" aria-label="关闭">×</button>
        <h3>登录 / 注册</h3>
        <p class="plm-sub">输入手机号即可一步完成登录或注册。还没有账号？自动创建。</p>
        <div v-if="error" class="plm-error"><strong>提示</strong>{{ error }}</div>
        <div class="plm-field">
          <label>手机号</label>
          <input type="tel" placeholder="请输入 11 位手机号" :maxlength="11" autocomplete="tel"
            :value="phone" @input="phone = $event.target.value.replace(/\D/g, '').slice(0, 11)" />
        </div>
        <div class="plm-field">
          <label>验证码</label>
          <div class="plm-field-row">
            <input type="text" placeholder="6 位验证码" :maxlength="6" inputmode="numeric"
              :value="code" @input="code = $event.target.value.replace(/\D/g, '').slice(0, 6)" />
            <button class="plm-btn plm-btn-ghost" :disabled="countdown > 0 || sending" @click="sendCode">
              {{ sending ? '发送中...' : countdown > 0 ? `重新发送 ${countdown}s` : '获取验证码' }}
            </button>
          </div>
        </div>
        <button class="plm-btn plm-btn-primary plm-submit" :disabled="loading" @click="submit">
          {{ loading ? '登录中...' : '登录 / 注册' }}
        </button>
        <div class="plm-foot">
          提交即表示同意 <a href="/terms" target="_blank">《用户协议》</a> 和 <a href="/privacy" target="_blank">《隐私政策》</a>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
/**
 * 手机号验证码登录弹窗（Landing / 实战营等公开页共用）。
 * 登录成功后 emit('success')，后续跳路由 / 开支付等由调用方决定。
 */
import { ref, watch, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { sendSmsCode, loginByPhone } from '@/api/auth'
import { useUserStore } from '@/stores/user'

const props = defineProps({
  open: { type: Boolean, default: false }
})
const emit = defineEmits(['update:open', 'success'])
const userStore = useUserStore()

const phone = ref('')
const code = ref('')
const error = ref('')
const countdown = ref(0)
const loading = ref(false)
const sending = ref(false)
let countdownTimer = null

const clearCountdown = () => {
  if (countdownTimer) {
    clearInterval(countdownTimer)
    countdownTimer = null
  }
}

const startCountdown = (seconds = 60) => {
  clearCountdown()
  countdown.value = seconds
  countdownTimer = setInterval(() => {
    if (countdown.value <= 1) {
      countdown.value = 0
      clearCountdown()
      return
    }
    countdown.value -= 1
  }, 1000)
}

// 每次打开都回到干净的表单
watch(() => props.open, (val) => {
  if (!val) return
  clearCountdown()
  phone.value = ''
  code.value = ''
  error.value = ''
  countdown.value = 0
  loading.value = false
  sending.value = false
})

const close = () => emit('update:open', false)

const sendCode = async () => {
  if (!/^1[3-9]\d{9}$/.test(phone.value)) {
    error.value = '请输入 11 位有效手机号'
    return
  }
  error.value = ''
  sending.value = true
  try {
    await sendSmsCode(phone.value)
    ElMessage.success('验证码已发送，请注意查收')
    startCountdown()
  } catch (e) {
    error.value = e.response?.data?.detail || '发送失败，请稍后重试'
  } finally {
    sending.value = false
  }
}

const submit = async () => {
  if (!/^1[3-9]\d{9}$/.test(phone.value)) {
    error.value = '请输入 11 位有效手机号'
    return
  }
  if (!/^\d{6}$/.test(code.value)) {
    error.value = '请输入 6 位验证码'
    return
  }
  error.value = ''
  loading.value = true
  try {
    const res = await loginByPhone(phone.value, code.value)
    const { access_token, refresh_token } = res.data
    userStore.token = access_token
    userStore.refreshToken = refresh_token
    localStorage.setItem('token', access_token)
    localStorage.setItem('refreshToken', refresh_token)
    localStorage.setItem('tokenSavedAt', String(Date.now()))
    await userStore.fetchUser()
    clearCountdown()
    ElMessage.success('登录成功')
    emit('update:open', false)
    emit('success')
  } catch (e) {
    error.value = e.response?.data?.detail || '登录失败，请检查验证码'
  } finally {
    loading.value = false
  }
}

onUnmounted(clearCountdown)
</script>

<style scoped>
/* 样式与 Landing 登录弹窗一致（plm- 前缀避免与页面样式互相污染） */
.plm-backdrop {
  position: fixed; inset: 0; background: rgba(31,31,30,.55);
  backdrop-filter: blur(4px); -webkit-backdrop-filter: blur(4px);
  z-index: 100; display: flex;
  align-items: center; justify-content: center; padding: 24px;
  animation: plm-fadeIn .2s ease;
}
@keyframes plm-fadeIn { from { opacity: 0; } to { opacity: 1; } }
.plm-modal {
  background: var(--paper); border-radius: var(--r-xl);
  padding: 40px; max-width: 440px; width: 100%; position: relative;
  box-shadow: var(--sh-3); animation: plm-slideUp .25s cubic-bezier(.2,.8,.2,1);
}
@keyframes plm-slideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }
.plm-close {
  position: absolute; top: 16px; right: 16px;
  width: 32px; height: 32px; border: none; background: transparent;
  color: var(--ink-3); font-size: 22px; border-radius: 6px; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all .15s; line-height: 1;
}
.plm-close:hover { background: var(--bone); color: var(--ink); }
.plm-modal h3 { font-size: 24px; margin-bottom: 8px; }
.plm-sub { font-size: 13.5px; color: var(--ink-3); margin-bottom: 28px; line-height: 1.65; }
.plm-field { margin-bottom: 14px; }
.plm-field label { display: block; font-size: 12.5px; color: var(--ink-2); margin-bottom: 6px; font-weight: 500; }
.plm-field-row { display: flex; gap: 8px; }
.plm-field input {
  width: 100%; height: 44px; padding: 0 14px;
  background: var(--ivory); border: 1px solid var(--line);
  border-radius: var(--r-sm); font-size: 14px; font-family: inherit;
  color: var(--ink); transition: all .15s;
}
.plm-field input:focus { outline: none; border-color: var(--clay); box-shadow: 0 0 0 3px rgba(204,120,92,.15); }
.plm-field-row .plm-btn { flex-shrink: 0; height: 44px; padding: 0 16px; min-width: 108px; }
.plm-field-row .plm-btn:disabled { opacity: .6; cursor: not-allowed; }
.plm-btn {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px;
  padding: 0 18px; height: 40px; border-radius: var(--r-md);
  font-size: 14px; font-weight: 500; font-family: inherit;
  border: 1px solid transparent; cursor: pointer;
  transition: all .15s ease; white-space: nowrap; letter-spacing: .01em;
}
.plm-btn-primary { background: var(--clay); color: #fff; box-shadow: var(--sh-clay); }
.plm-btn-primary:hover { background: var(--clay-deep); transform: translateY(-1px); }
.plm-btn-primary:active { transform: translateY(0); }
.plm-btn-ghost { background: transparent; color: var(--ink); border-color: var(--line); }
.plm-btn-ghost:hover { background: var(--bone); border-color: var(--line-2); }
.plm-submit { width: 100%; height: 44px; margin-top: 8px; font-size: 14.5px; }
.plm-foot {
  text-align: center; margin-top: 20px; padding-top: 20px;
  border-top: 1px dashed var(--line-2); font-size: 12.5px; color: var(--ink-3); line-height: 1.65;
}
.plm-foot a { color: var(--clay-deep); border-bottom: 1px solid var(--clay-soft); }
.plm-error {
  margin-bottom: 18px; padding: 14px 16px;
  background: #FFF4F0; border: 1px solid var(--clay-soft);
  border-left: 3px solid var(--clay); border-radius: var(--r-sm);
  font-size: 13px; line-height: 1.65; color: var(--ink);
}
.plm-error strong { display: block; color: var(--clay-deep); margin-bottom: 4px; font-size: 14px; }
</style>
