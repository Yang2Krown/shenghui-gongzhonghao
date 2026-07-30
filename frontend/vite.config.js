import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src')
    }
  },
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api')
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    // 生产包不公开源码映射，避免泄露源码并减少静态资源体积。
    // 如需错误追踪，应改为上传到私有监控服务，而不是随 dist 一起发布。
    sourcemap: false,
    rollupOptions: {
      output: {
        // 将稳定的第三方依赖单独缓存，避免业务页面变动时重复下载整块 vendor。
        manualChunks: {
          'vendor-vue': ['vue', 'vue-router', 'pinia'],
          'vendor-element': ['element-plus', '@element-plus/icons-vue'],
          'vendor-editor': ['@wangeditor/editor', '@wangeditor/editor-for-vue', '@tiptap/starter-kit', '@tiptap/vue-3'],
          'vendor-markdown': ['marked'],
          'vendor-utils': ['axios', 'qrcode']
        }
      }
    }
  }
})
