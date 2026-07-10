<template>
  <router-view />
  <el-dialog
    v-model="announcementVisible"
    class="system-announcement-dialog"
    width="520px"
    :close-on-click-modal="false"
    :close-on-press-escape="false"
    :show-close="false"
    align-center
  >
    <template #header>
      <div class="announcement-title">📣 {{ currentAnnouncement?.title || '系统公告' }}</div>
    </template>
    <div class="announcement-content">{{ currentAnnouncement?.content }}</div>
    <div class="announcement-expiry">提示有效至 {{ formatAnnouncementTime(currentAnnouncement?.expires_at) }}</div>
    <template #footer>
      <el-button :loading="dismissing" @click="stopReminding">不再提示</el-button>
      <el-button type="primary" @click="confirmAnnouncement">确认收到</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useUserStore } from '@/stores/user'
import { dismissAnnouncement, getActiveAnnouncements } from '@/api/announcements'

const userStore = useUserStore()
const announcements = ref([])
const dismissing = ref(false)
const currentAnnouncement = computed(() => announcements.value[0] || null)
const announcementVisible = computed({
  get: () => Boolean(currentAnnouncement.value),
  set: () => {},
})

const fetchAnnouncements = async () => {
  if (!userStore.isAuthenticated || !userStore.user?.id) return
  try {
    const res = await getActiveAnnouncements()
    announcements.value = res.data.items || []
  } catch {
    // 请求失败由统一拦截器处理；公告不影响正常使用。
  }
}

const confirmAnnouncement = () => {
  // “确认收到”只关闭本次显示；下次登录仍会再次提示。
  announcements.value.shift()
}

const stopReminding = async () => {
  if (!currentAnnouncement.value) return
  dismissing.value = true
  try {
    await dismissAnnouncement(currentAnnouncement.value.id)
    announcements.value.shift()
  } catch {
    // 请求失败时保持弹窗，避免错误地当作已设置成功。
  } finally {
    dismissing.value = false
  }
}

const formatAnnouncementTime = (value) => value
  ? new Date(value).toLocaleString('zh-CN', { dateStyle: 'medium', timeStyle: 'short' })
  : '-'

onMounted(async () => {
  // 初始化时检查用户登录状态
  await userStore.initialize()
  await fetchAnnouncements()
})

// 短信登录成功后 App 不会重新挂载，监听用户切换以补拉公告。
watch(() => userStore.user?.id, (userId, previousUserId) => {
  if (userId && userId !== previousUserId) fetchAnnouncements()
  if (!userId) announcements.value = []
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

.system-announcement-dialog .el-dialog__header {
  margin-right: 0;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--line);
}

.announcement-title { font-size: 18px; font-weight: 700; color: var(--ink); }
.announcement-content { white-space: pre-wrap; line-height: 1.8; color: var(--ink-2); min-height: 72px; }
.announcement-expiry { margin-top: 20px; font-size: 12px; color: var(--ink-4); }
</style>
