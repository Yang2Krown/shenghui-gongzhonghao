<template>
  <div class="min-h-screen bg-ivory">
    <!-- 侧边栏 -->
    <el-aside :width="isCollapsed ? '64px' : '240px'" class="fixed left-0 top-0 bottom-0 bg-paper shadow-sh-1 border-r border-line transition-all duration-300 z-30">
      <div class="flex flex-col h-full">
        <!-- Logo区域 -->
        <div class="flex items-center justify-center h-16 border-b border-line">
          <div v-if="!isCollapsed" class="flex items-center space-x-2">
            <div class="w-8 h-8 bg-clay rounded-r-md flex items-center justify-center">
              <span class="text-paper font-bold text-lg">AI</span>
            </div>
            <span class="text-lg font-bold text-ink">内容运营平台</span>
          </div>
          <div v-else class="w-8 h-8 bg-clay rounded-r-md flex items-center justify-center">
            <span class="text-paper font-bold text-lg">AI</span>
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

          <el-menu-item index="creation">
            <el-icon><Edit /></el-icon>
            <template #title>我的创作</template>
          </el-menu-item>

          <el-menu-item index="custom-topic">
            <el-icon><EditPen /></el-icon>
            <template #title>自定义选题</template>
          </el-menu-item>

          <el-sub-menu index="titles">
            <template #title>
              <el-icon><ChatDotSquare /></el-icon>
              <span>标题工具</span>
            </template>
            <el-menu-item index="standalone-title">智能起标题</el-menu-item>
            <!-- 芒格标题生成入口暂时隐藏（路由与页面代码保留） -->
            <!-- <el-menu-item index="munger-generation">芒格标题生成</el-menu-item> -->
            <el-menu-item index="munger-scorer">芒格标题评分</el-menu-item>
          </el-sub-menu>

          <el-menu-item index="wechat-to-xhs">
            <el-icon><Switch /></el-icon>
            <template #title>公众号转小红书</template>
          </el-menu-item>

          <el-menu-item index="history">
            <el-icon><Clock /></el-icon>
            <template #title>生成记录</template>
          </el-menu-item>

          <!-- 底部分隔 -->
          <div class="flex-1"></div>

          <el-menu-item index="settings">
            <el-icon><Setting /></el-icon>
            <template #title>设置</template>
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
        <router-view v-slot="{ Component }">
          <keep-alive :include="['TopicClusters']">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </el-main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { Edit, Setting, SwitchButton, ArrowDown, Expand, Fold, DataBoard, Folder, Document, ChatDotSquare, Switch, EditPen, Clock } from '@element-plus/icons-vue'

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
  if (path.startsWith('/creation')) return 'creation'
  if (path.startsWith('/custom-topic')) return 'custom-topic'
  if (path.startsWith('/settings')) return 'settings'
  if (path.startsWith('/standalone-title') || path.startsWith('/munger-generation') || path.startsWith('/munger-scorer')) return 'titles'
  if (path.startsWith('/wechat-to-xhs')) return 'wechat-to-xhs'
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
    'creation': '/creation',
    'custom-topic': '/custom-topic',
    'settings': '/settings',
    'standalone-title': '/standalone-title',
    'munger-generation': '/munger-generation',
    'munger-scorer': '/munger-scorer',
    'wechat-to-xhs': '/wechat-to-xhs',
    'history': '/history',
  }

  if (index === 'titles') {
    return // sub-menu header, do nothing
  }

  if (menuRoutes[index]) {
    router.push(menuRoutes[index])
  }
}

// 用户命令处理
const handleUserCommand = (command) => {
  switch (command) {
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
