<template>
  <div class="min-h-screen bg-ivory">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapsed ? '64px' : '240px'" class="fixed left-0 top-0 bottom-0 bg-paper shadow-sh-1 border-r border-line transition-all duration-300 z-30">
      <div class="flex flex-col h-full">
        <!-- Logo区域 -->
        <div class="flex items-center justify-center h-16 border-b border-line">
          <div v-if="!isCollapsed" class="flex items-center space-x-2">
            <div class="w-8 h-8 bg-clay rounded-r-md flex items-center justify-center">
              <span class="text-white font-bold text-lg">AI</span>
            </div>
            <span class="text-lg font-bold text-ink">内容运营平台</span>
          </div>
          <div v-else class="w-8 h-8 bg-clay rounded-r-md flex items-center justify-center">
            <span class="text-white font-bold text-lg">AI</span>
          </div>
        </div>
        
        <!-- 导航菜单 -->
        <el-menu
          :default-active="activeMenu"
          :collapse="isCollapsed"
          class="flex-1 border-none"
          @select="handleMenuSelect"
        >
          <el-menu-item index="topic-clusters">
            <el-icon><Folder /></el-icon>
            <template #title>话题库</template>
          </el-menu-item>

          <el-menu-item index="topic-candidates">
            <el-icon><DataBoard /></el-icon>
            <template #title>候选选题</template>
          </el-menu-item>

          <el-menu-item index="outlines">
            <el-icon><Document /></el-icon>
            <template #title>大纲管理</template>
          </el-menu-item>

          <el-menu-item index="title-generation">
            <el-icon><MagicStick /></el-icon>
            <template #title>标题生成</template>
          </el-menu-item>

          <el-menu-item index="content-generation">
            <el-icon><Notebook /></el-icon>
            <template #title>正文生成</template>
          </el-menu-item>

          <el-menu-item index="creation">
            <el-icon><Edit /></el-icon>
            <template #title>我的创作</template>
          </el-menu-item>
          
          <el-menu-item index="settings">
            <el-icon><Setting /></el-icon>
            <template #title>个人设置</template>
          </el-menu-item>
          
          <el-menu-item index="style-settings">
            <el-icon><Brush /></el-icon>
            <template #title>风格设置</template>
          </el-menu-item>
        </el-menu>
        
        <!-- 用户信息 -->
        <div class="p-4 border-t border-line">
          <div v-if="userStore.user" class="flex items-center space-x-3">
            <el-avatar :size="32" :src="userStore.user.avatar_url" class="flex-shrink-0">
              {{ userStore.user.username?.charAt(0)?.toUpperCase() }}
            </el-avatar>
            <div v-if="!isCollapsed" class="flex-1 min-w-0">
              <p class="text-sm font-medium text-ink truncate">
                {{ userStore.user.full_name || userStore.user.username }}
              </p>
              <p class="text-xs text-ink-3 truncate">
                {{ userStore.user.email }}
              </p>
            </div>
          </div>
          <div v-else class="flex items-center justify-center">
            <el-button type="primary" @click="$router.push('/login')">
              登录
            </el-button>
          </div>
        </div>
      </div>
    </el-aside>
    
    <!-- 主内容区 -->
    <div :style="{ marginLeft: isCollapsed ? '64px' : '240px' }" class="transition-all duration-300">
      <!-- 顶部导航栏 -->
      <el-header class="fixed top-0 right-0 bg-paper shadow-sh-1 border-b border-line z-20 flex items-center justify-between px-6" :style="{ left: isCollapsed ? '64px' : '240px' }">
        <div class="flex items-center space-x-4">
          <!-- 折叠按钮 -->
          <el-button
            :icon="isCollapsed ? 'Expand' : 'Fold'"
            text
            @click="toggleSidebar"
            class="text-ink-3 hover:text-ink"
          />
          
          <!-- 面包屑导航 -->
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ path: '/' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-for="(item, index) in breadcrumbs" :key="index" :to="item.path">
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <div class="flex items-center space-x-4">
          <!-- 通知图标 -->
          <el-badge :value="3" :max="99" class="mr-4">
            <el-icon :size="20" class="text-ink-3 hover:text-ink cursor-pointer">
              <Bell />
            </el-icon>
          </el-badge>
          
          <!-- 用户下拉菜单 -->
          <el-dropdown v-if="userStore.user" @command="handleUserCommand">
            <div class="flex items-center space-x-2 cursor-pointer">
              <el-avatar :size="28" :src="userStore.user.avatar_url">
                {{ userStore.user.username?.charAt(0)?.toUpperCase() }}
              </el-avatar>
              <span class="text-sm text-ink-2">
                {{ userStore.user.full_name || userStore.user.username }}
              </span>
              <el-icon class="text-ink-4">
                <ArrowDown />
              </el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>
                  个人资料
                </el-dropdown-item>
                <el-dropdown-item command="settings">
                  <el-icon><Setting /></el-icon>
                  设置
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      
      <!-- 页面内容 -->
      <el-main class="pt-20 pb-8 px-6">
        <router-view />
      </el-main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { Document, Edit, Setting, Brush, Bell, User, SwitchButton, ArrowDown, Expand, Fold, DataBoard, Folder, MagicStick, Notebook } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

// 侧边栏折叠状态
const isCollapsed = ref(false)

// 当前激活的菜单
const activeMenu = computed(() => {
  const path = route.path
  if (path === '/' || path.startsWith('/topic-clusters')) return 'topic-clusters'
  if (path.startsWith('/topic-candidates')) return 'topic-candidates'
  if (path.startsWith('/outlines')) return 'outlines'
  if (path.startsWith('/title-generation') || path.startsWith('/title-history')) return 'title-generation'
  if (path.startsWith('/content-generation')) return 'content-generation'
  if (path.startsWith('/creation')) return 'creation'
  if (path === '/settings') return 'settings'
  if (path === '/settings/style') return 'style-settings'
  return 'topic-clusters'
})

// 面包屑导航
const breadcrumbs = computed(() => {
  const matched = route.matched.filter(item => item.meta && item.meta.title)
  return matched.map(item => ({
    title: item.meta.title,
    path: item.path
  }))
})

// 切换侧边栏
const toggleSidebar = () => {
  isCollapsed.value = !isCollapsed.value
}

// 菜单选择处理
const handleMenuSelect = (index) => {
  const menuRoutes = {
    'topic-clusters': '/topic-clusters',
    'topic-candidates': '/topic-candidates',
    'outlines': '/outlines',
    'title-generation': '/title-generation',
    'content-generation': '/content-generation',
    'creation': '/creation',
    'settings': '/settings',
    'style-settings': '/settings/style'
  }

  if (menuRoutes[index]) {
    router.push(menuRoutes[index])
  }
}

// 用户命令处理
const handleUserCommand = (command) => {
  switch (command) {
    case 'profile':
      router.push('/settings')
      break
    case 'settings':
      router.push('/settings')
      break
    case 'logout':
      userStore.logout()
      router.push('/login')
      break
  }
}

// 监听路由变化，更新面包屑
watch(route, () => {
  // 路由变化时的处理
}, { immediate: true })
</script>

<style scoped>
.el-aside {
  overflow: hidden;
}

.el-menu {
  border-right: none;
}

.el-menu-item {
  height: 50px;
  line-height: 50px;
}

.el-menu-item.is-active {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

.el-header {
  height: 64px;
  line-height: 64px;
}
</style>