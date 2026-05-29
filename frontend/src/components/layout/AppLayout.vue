<template>
  <div class="min-h-screen bg-ivory">
    <!-- 侧边栏 -->
    <aside class="sidebar">
      <!-- Logo -->
      <div class="sidebar-logo">
        <div class="logo-icon">公</div>
        <div>
          <div class="logo-title">公众号创作台</div>
          <div class="logo-sub">AI Content Studio</div>
        </div>
      </div>
      <div class="divider" style="margin: 0 16px"></div>

      <!-- 导航 -->
      <nav class="sidebar-nav">
        <NavItem
          :active="activeMenu === 'feed'"
          icon="Document"
          label="内容资讯"
          @click="go('feed')"
        />

        <!-- 创作工具 -->
        <div class="nav-group">
          <button class="nav-group-header" @click="toggleGroup('create')">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 6a3.5 3.5 0 0 0-4.9 4.4L3 17v4h4l6.6-6.6A3.5 3.5 0 0 0 18 9.5"/><circle cx="17" cy="7" r="0.5" fill="currentColor"/></svg>
            <span>创作工具</span>
            <svg class="chevron" :class="{ open: openGroups.create }" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
          </button>
          <div v-show="openGroups.create" class="nav-group-items">
            <NavItem :active="activeMenu === 'angle'" icon="View" label="创作角度" indent @click="go('angle')" />
            <NavItem :active="activeMenu === 'outline'" icon="List" label="大纲生成" indent @click="go('outline')" />
            <NavItem :active="activeMenu === 'body'" icon="Document" label="正文生成" indent @click="go('body')" />
            <NavItem :active="activeMenu === 'title'" icon="ChatDotSquare" label="标题生成" indent @click="go('title')" />
          </div>
        </div>

        <!-- 内容仿写 -->
        <div class="nav-group">
          <button class="nav-group-header" @click="toggleGroup('rewrite')">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7"/></svg>
            <span>内容仿写</span>
            <svg class="chevron" :class="{ open: openGroups.rewrite }" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
          </button>
          <div v-show="openGroups.rewrite" class="nav-group-items">
            <NavItem :active="activeMenu === 'wechat-to-xhs'" icon="Switch" label="公众号转小红书" indent @click="go('wechat-to-xhs')" />
            <NavItem :active="activeMenu === 'wechat-rewrite'" icon="Edit" label="公众号仿写" indent @click="go('wechat-rewrite')" />
            <NavItem :active="activeMenu === 'xhs-to-wechat'" icon="Switch" label="小红书转公众号" indent @click="go('xhs-to-wechat')" />
            <NavItem :active="activeMenu === 'douyin-to-wechat'" icon="Switch" label="抖音转公众号" indent @click="go('douyin-to-wechat')" />
            <NavItem :active="activeMenu === 'zhihu-to-wechat'" icon="Switch" label="知乎转公众号" indent @click="go('zhihu-to-wechat')" />
            <NavItem :active="activeMenu === 'content-rewrite'" icon="Document" label="内容仿写" indent @click="go('content-rewrite')" />
          </div>
        </div>

        <NavItem :active="activeMenu === 'history'" icon="Clock" label="创作历史" @click="go('history')" />
        <NavItem :active="activeMenu === 'profile'" icon="User" label="个人信息" @click="go('profile')" />
      </nav>

      <!-- 用户信息 -->
      <div class="sidebar-user">
        <button class="user-btn" @click="go('profile')">
          <div class="user-avatar">{{ userStore.user?.username?.charAt(0)?.toUpperCase() || '用' }}</div>
          <div class="user-info">
            <div class="user-name">{{ userStore.user?.full_name || userStore.user?.username || '用户' }}</div>
            <div class="user-role">专业版</div>
          </div>
        </button>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="main-wrapper">
      <header class="topbar">
        <div class="breadcrumb">
          <span>首页</span>
          <template v-if="breadcrumb.group">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
            <span>{{ breadcrumb.group }}</span>
          </template>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>
          <span class="breadcrumb-current">{{ breadcrumb.label }}</span>
        </div>
        <div class="topbar-right">
          <el-dropdown v-if="userStore.user" @command="handleUserCommand">
            <div class="topbar-user">
              <el-avatar :size="28" :src="userStore.user?.avatar_url">
                {{ userStore.user?.username?.charAt(0)?.toUpperCase() }}
              </el-avatar>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">个人信息</el-dropdown-item>
                <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="main-content">
        <router-view v-slot="{ Component }">
          <keep-alive>
            <component :is="Component" :key="$route.path" />
          </keep-alive>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import NavItem from './NavItem.vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const openGroups = ref({ create: true, rewrite: true })

const toggleGroup = (id) => {
  openGroups.value[id] = !openGroups.value[id]
}

const ROUTE_MAP = {
  'feed': '/',
  'angle': '/angle',
  'outline': '/outline',
  'body': '/body',
  'title': '/title',
  'wechat-to-xhs': '/wechat-to-xhs',
  'wechat-rewrite': '/wechat-rewrite',
  'xhs-to-wechat': '/xhs-to-wechat',
  'douyin-to-wechat': '/douyin-to-wechat',
  'zhihu-to-wechat': '/zhihu-to-wechat',
  'content-rewrite': '/content-rewrite',
  'history': '/history',
  'profile': '/profile',
}

const go = (id) => {
  const path = ROUTE_MAP[id]
  if (path) router.push(path)
}

const NAV_LABELS = {
  'feed': { group: null, label: '内容资讯' },
  'angle': { group: '创作工具', label: '创作角度' },
  'outline': { group: '创作工具', label: '大纲生成' },
  'body': { group: '创作工具', label: '正文生成' },
  'title': { group: '创作工具', label: '标题生成' },
  'wechat-to-xhs': { group: '内容仿写', label: '公众号转小红书' },
  'wechat-rewrite': { group: '内容仿写', label: '公众号仿写' },
  'xhs-to-wechat': { group: '内容仿写', label: '小红书转公众号' },
  'douyin-to-wechat': { group: '内容仿写', label: '抖音转公众号' },
  'zhihu-to-wechat': { group: '内容仿写', label: '知乎转公众号' },
  'content-rewrite': { group: '内容仿写', label: '内容仿写' },
  'history': { group: null, label: '创作历史' },
  'profile': { group: null, label: '个人信息' },
}

const activeMenu = computed(() => {
  const path = route.path
  if (path === '/' || path === '/feed') return 'feed'
  for (const key of Object.keys(ROUTE_MAP)) {
    if (ROUTE_MAP[key] === path) return key
  }
  return 'feed'
})

const breadcrumb = computed(() => NAV_LABELS[activeMenu.value] || { group: null, label: '内容资讯' })

const handleUserCommand = (cmd) => {
  if (cmd === 'profile') go('profile')
  else if (cmd === 'logout') {
    userStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.sidebar {
  width: 248px;
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  background: var(--paper);
  border-right: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  z-index: 30;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 20px 20px 16px;
}

.logo-icon {
  width: 34px;
  height: 34px;
  border-radius: 8px 3px 8px 8px;
  background: var(--clay);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  font-family: var(--serif);
}

.logo-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--ink);
  line-height: 1.1;
}

.logo-sub {
  font-size: 12px;
  color: var(--ink-4);
  letter-spacing: 0.04em;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 14px 12px;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.nav-group-header {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  padding: 10px 14px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: var(--r-md);
  font-family: inherit;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-2);
  transition: color 0.14s;
}

.nav-group-header:hover {
  color: var(--ink);
}

.chevron {
  margin-left: auto;
  transition: transform 0.18s;
  color: var(--ink-4);
}

.chevron.open {
  transform: rotate(90deg);
}

.nav-group-items {
  display: flex;
  flex-direction: column;
  gap: 2px;
  margin-top: 2px;
}

.sidebar-user {
  padding: 14px;
  border-top: 1px solid var(--line);
}

.user-btn {
  display: flex;
  align-items: center;
  gap: 11px;
  width: 100%;
  padding: 8px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: var(--r-md);
  font-family: inherit;
  transition: background 0.14s;
}

.user-btn:hover {
  background: var(--bone);
}

.user-avatar {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  background: var(--clay);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-family: var(--serif);
  flex-shrink: 0;
  font-size: 14px;
}

.user-info {
  text-align: left;
  min-width: 0;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-role {
  font-size: 12px;
  color: var(--ink-4);
}

.main-wrapper {
  margin-left: 248px;
}

.topbar {
  position: fixed;
  top: 0;
  left: 248px;
  right: 0;
  height: 60px;
  background: rgba(250, 249, 245, 0.85);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--line);
  z-index: 20;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 32px;
}

.breadcrumb {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--ink-4);
}

.breadcrumb-current {
  font-weight: 600;
  color: var(--ink-2);
}

.topbar-right {
  display: flex;
  align-items: center;
}

.topbar-user {
  cursor: pointer;
  display: flex;
  align-items: center;
}

.main-content {
  padding-top: 60px;
}

.main-content > :deep(*) {
  padding: 32px 32px 80px;
}

.divider {
  height: 1px;
  background: var(--line);
  border: 0;
}
</style>
