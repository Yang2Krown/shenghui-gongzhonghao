<template>
  <div class="profile-card feishu-connect-card">
    <div class="integration-card-inner">
      <div class="integration-card-header">
        <div>
          <h3>飞书绑定</h3>
          <p>连接后可一键导入飞书 brief，自动生成写作要求</p>
        </div>

        <!-- 已绑定 -->
        <el-button v-if="status === 'valid'" text type="danger" @click="logout" :loading="loggingOut">解除绑定</el-button>
        <!-- 未绑定 / 失效 -->
        <el-button v-else-if="status !== 'pending'" type="primary" @click="connect" :loading="connecting">
          {{ status === 'expired' ? '重新连接飞书' : '连接飞书' }}
        </el-button>
      </div>

      <!-- 已绑定身份 -->
      <div v-if="status === 'valid'" class="feishu-bound integration-status">
        <el-icon class="bound-icon"><CircleCheck /></el-icon>
        <span>已绑定：<b>{{ feishuUserName || '飞书账号' }}</b></span>
        <span v-if="authorizedAt" class="feishu-meta">· {{ formatTime(authorizedAt) }}</span>
      </div>

      <!-- 授权进行中 -->
      <div v-else-if="status === 'pending'" class="feishu-pending integration-status">
        <div class="feishu-pending-head">
          <el-icon class="is-loading"><Loading /></el-icon>
          <span>等待在飞书中确认授权…</span>
        </div>
        <p class="feishu-tip">如果没自动弹出授权页，点下面按钮打开（链接 10 分钟内有效）：</p>
        <div class="feishu-actions">
          <el-button size="small" type="primary" @click="openVerifyUrl" :disabled="!verifyUrl">打开授权页</el-button>
          <el-button size="small" text @click="cancelPending" :loading="cancelling">取消</el-button>
        </div>
      </div>

      <!-- 未绑定提示 -->
      <div v-else class="feishu-hint integration-empty">
        <p>尚未绑定飞书账号</p>
        <p>绑定后即可在创作页一键导入飞书 brief。</p>
        <p v-if="lastError" class="feishu-error">上次失败：{{ lastError }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { CircleCheck, Loading } from '@element-plus/icons-vue'
import { feishuAuthStart, feishuAuthStatus, feishuAuthLogout, feishuAuthCancel } from '@/api/feishu'

const unwrap = (res) => (res && res.data !== undefined ? res.data : res)

const status = ref('none')          // none | pending | valid | expired
const feishuUserName = ref('')
const authorizedAt = ref('')
const lastError = ref('')
const verifyUrl = ref('')
const connecting = ref(false)
const loggingOut = ref(false)
const cancelling = ref(false)

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
    } else if (Date.now() > pollDeadline) {
      stopPolling()
      await cancelPending({ silent: true })
      ElMessage.warning('飞书授权已超时，请重新连接')
    } else if (s !== 'pending') {
      stopPolling()
      status.value = s || 'none'
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

const resetPendingState = () => {
  status.value = 'none'
  verifyUrl.value = ''
  feishuUserName.value = ''
  authorizedAt.value = ''
}

const cancelPending = async ({ silent = false } = {}) => {
  stopPolling()
  cancelling.value = true
  try {
    await feishuAuthCancel()
    resetPendingState()
    if (!silent) ElMessage.success('已取消飞书授权')
  } catch (e) {
    ElMessage.error('取消授权失败')
    await refreshStatus()
  } finally {
    cancelling.value = false
  }
}

const logout = async () => {
  loggingOut.value = true
  try {
    await feishuAuthLogout()
    resetPendingState()
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
.integration-card-inner { padding: 2px 0; }
.integration-card-header { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin-bottom: 22px; }
.integration-card-header h3 { margin: 0 0 5px; color: var(--ink); font-size: 17px; font-weight: 600; }
.integration-card-header p { margin: 0; color: var(--ink-4); font-size: 13px; line-height: 1.6; }
.integration-empty { display: flex; min-height: 145px; align-items: center; justify-content: center; flex-direction: column; border: 1px dashed var(--line, #e5e5e5); border-radius: 12px; background: var(--paper-2, #faf9f7); text-align: center; }
.integration-empty p { margin: 0; color: var(--ink-4); font-size: 13px; line-height: 1.6; }
.integration-empty p:first-child { margin-bottom: 4px; color: var(--ink-3); font-size: 14px; }
.integration-status { box-sizing: border-box; }
.feishu-bound {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-start;
  height: 84px;
  min-height: 84px;
  padding: 14px 18px;
  border: 1px solid var(--line, #e5e5e5);
  border-radius: 10px;
  background: var(--paper, #fff);
  font-size: 13px;
  color: var(--ink-2, #3a3935);
}
.feishu-bound .bound-icon { flex-shrink: 0; color: var(--leaf, #6b8e6b); }
.feishu-meta { color: var(--ink-4); font-size: 12px; }
.feishu-pending { background: var(--paper-2, #faf9f7); border: 1px solid var(--line, #eee); border-radius: 10px; padding: 14px 16px; }
.feishu-pending-head { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--ink); margin-bottom: 6px; }
.feishu-tip { font-size: 12px; color: var(--ink-4); margin-bottom: 10px; }
.feishu-actions { display: flex; gap: 8px; }
.feishu-error { color: #dc2626; margin-top: 4px; }
@media (max-width: 768px) {
  .integration-card-header { align-items: flex-start; }
  .feishu-bound { height: auto; min-height: 0; }
}
</style>
