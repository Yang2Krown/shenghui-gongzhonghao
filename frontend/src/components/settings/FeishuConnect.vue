<template>
  <div class="profile-card">
    <div style="padding: 24px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px;">
        <div>
          <h3 style="font-size: 17px; font-weight: 600; color: var(--ink); margin-bottom: 4px;">飞书绑定</h3>
          <p style="font-size: 13px; color: var(--ink-4);">连接飞书后，可直接粘贴客户的飞书 brief 链接，自动读取并解析成写作要求</p>
        </div>

        <!-- 已绑定 -->
        <el-button v-if="status === 'valid'" text type="danger" @click="logout" :loading="loggingOut">解除绑定</el-button>
        <!-- 未绑定 / 失效 -->
        <el-button v-else-if="status !== 'pending'" type="primary" @click="connect" :loading="connecting">
          {{ status === 'expired' ? '重新连接飞书' : '连接飞书' }}
        </el-button>
      </div>

      <!-- 已绑定身份 -->
      <div v-if="status === 'valid'" class="feishu-bound">
        <el-icon color="#16a34a"><CircleCheck /></el-icon>
        <span>已绑定：<b>{{ feishuUserName || '飞书账号' }}</b></span>
        <span v-if="authorizedAt" class="feishu-meta">· {{ formatTime(authorizedAt) }}</span>
      </div>

      <!-- 授权进行中 -->
      <div v-else-if="status === 'pending'" class="feishu-pending">
        <div class="feishu-pending-head">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>等待在飞书中确认授权…</span>
        </div>
        <p class="feishu-tip">如果没自动弹出授权页，点下面按钮打开（链接 10 分钟内有效）：</p>
        <div class="feishu-actions">
          <el-button size="small" type="primary" @click="openVerifyUrl" :disabled="!verifyUrl">打开授权页</el-button>
          <el-button size="small" text @click="cancelPending">取消</el-button>
        </div>
      </div>

      <!-- 未绑定提示 -->
      <div v-else class="feishu-hint">
        <p>尚未绑定。绑定后即可在创作页一键导入飞书 brief。</p>
        <p v-if="lastError" class="feishu-error">上次失败：{{ lastError }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, Loading } from '@element-plus/icons-vue'
import { feishuAuthStart, feishuAuthStatus, feishuAuthLogout } from '@/api/feishu'

const unwrap = (res) => (res && res.data !== undefined ? res.data : res)

const status = ref('none')          // none | pending | valid | expired
const feishuUserName = ref('')
const authorizedAt = ref('')
const lastError = ref('')
const verifyUrl = ref('')
const connecting = ref(false)
const loggingOut = ref(false)

let pollTimer = null
let pollDeadline = 0

const refreshStatus = async () => {
  try {
    const d = unwrap(await feishuAuthStatus())
    status.value = d.status || 'none'
    feishuUserName.value = d.feishu_user_name || ''
    authorizedAt.value = d.authorized_at || ''
    lastError.value = d.last_error || ''
    return d.status
  } catch (e) {
    return null
  }
}

const startPolling = () => {
  stopPolling()
  pollDeadline = Date.now() + 11 * 60 * 1000   // 略大于授权链接有效期
  pollTimer = setInterval(async () => {
    const s = await refreshStatus()
    if (s === 'valid') {
      stopPolling()
      ElMessage.success(`飞书绑定成功：${feishuUserName.value || ''}`)
    } else if (s !== 'pending' || Date.now() > pollDeadline) {
      stopPolling()
      if (s !== 'valid') status.value = s || 'none'
    }
  }, 3000)
}

const stopPolling = () => {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

const openVerifyUrl = () => {
  if (verifyUrl.value) window.open(verifyUrl.value, '_blank')
}

const connect = async () => {
  connecting.value = true
  try {
    const d = unwrap(await feishuAuthStart())
    verifyUrl.value = d.verification_url || ''
    status.value = 'pending'
    openVerifyUrl()
    startPolling()
  } catch (e) {
    ElMessage.error(e?.response?.data?.detail || '发起飞书授权失败')
  } finally {
    connecting.value = false
  }
}

const cancelPending = () => {
  stopPolling()
  refreshStatus()
}

const logout = async () => {
  loggingOut.value = true
  try {
    await feishuAuthLogout()
    status.value = 'none'
    feishuUserName.value = ''
    ElMessage.success('已解除飞书绑定')
  } catch (e) {
    ElMessage.error('解除绑定失败')
  } finally {
    loggingOut.value = false
  }
}

const formatTime = (iso) => {
  try { return new Date(iso).toLocaleString('zh-CN', { hour12: false }) } catch { return '' }
}

onMounted(async () => {
  const s = await refreshStatus()
  if (s === 'pending') startPolling()   // 刷新页面后仍在等待授权
})
onUnmounted(stopPolling)
</script>

<style scoped>
.feishu-bound { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--ink); }
.feishu-meta { color: var(--ink-4); font-size: 12px; }
.feishu-pending { background: var(--paper-2, #faf9f7); border: 1px solid var(--line, #eee); border-radius: 10px; padding: 14px 16px; }
.feishu-pending-head { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--ink); margin-bottom: 6px; }
.feishu-tip { font-size: 12px; color: var(--ink-4); margin-bottom: 10px; }
.feishu-actions { display: flex; gap: 8px; }
.feishu-hint { font-size: 13px; color: var(--ink-4); }
.feishu-error { color: #dc2626; margin-top: 4px; }
</style>
