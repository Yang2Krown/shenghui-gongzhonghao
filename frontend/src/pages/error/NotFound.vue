<template>
  <div class="not-found-page min-h-screen bg-ivory flex flex-col justify-center py-12 sm:px-6 lg:px-8">
    <div class="sm:mx-auto sm:w-full sm:max-w-md">
      <div class="text-center">
        <!-- 404图标 -->
        <div class="text-9xl font-bold text-clay mb-4">404</div>
        
        <!-- 标题 -->
        <h1 class="text-h1 font-serif text-ink mb-4">
          页面未找到
        </h1>
        
        <!-- 描述 -->
        <p class="text-body text-ink-3 mb-8">
          抱歉，您访问的页面不存在或已被移除。
        </p>
        
        <!-- 操作按钮 -->
        <div class="flex flex-col sm:flex-row gap-4 justify-center">
          <el-button type="primary" size="large" @click="goHome">
            <el-icon><HomeFilled /></el-icon>
            返回首页
          </el-button>
          
          <el-button size="large" @click="goBack">
            <el-icon><Back /></el-icon>
            返回上一页
          </el-button>
        </div>
        
        <!-- 搜索 -->
        <div class="mt-12">
          <p class="text-ink-3 mb-4">或者尝试搜索：</p>
          <div class="max-w-md mx-auto">
            <el-input
              v-model="searchQuery"
              placeholder="搜索选题、创作..."
              size="large"
              @keyup.enter="handleSearch"
            >
              <template #append>
                <el-button @click="handleSearch">
                  <el-icon><Search /></el-icon>
                </el-button>
              </template>
            </el-input>
          </div>
        </div>
        
        <!-- 建议链接 -->
        <div class="mt-12">
          <p class="text-ink-3 mb-4">您可能想要访问：</p>
          <div class="flex flex-wrap justify-center gap-4">
            <router-link to="/" class="text-clay-deep hover:text-clay font-medium">
              每日选题
            </router-link>
            <router-link to="/creation" class="text-clay-deep hover:text-clay font-medium">
              我的创作
            </router-link>
            <router-link to="/settings" class="text-clay-deep hover:text-clay font-medium">
              个人设置
            </router-link>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { HomeFilled, Back, Search } from '@element-plus/icons-vue'

const router = useRouter()

// 搜索查询
const searchQuery = ref('')

// 返回首页
const goHome = () => {
  router.push('/')
}

// 返回上一页
const goBack = () => {
  router.go(-1)
}

// 处理搜索
const handleSearch = () => {
  if (searchQuery.value.trim()) {
    router.push({
      path: '/topics',
      query: { keyword: searchQuery.value.trim() }
    })
  }
}
</script>

<style scoped>
.not-found-page {
  background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
}

.text-9xl {
  font-size: 8rem;
  line-height: 1;
}

@media (max-width: 640px) {
  .text-9xl {
    font-size: 5rem;
  }
}
</style>