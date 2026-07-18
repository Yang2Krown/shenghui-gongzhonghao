/**
 * 计数式 body 滚动锁。
 *
 * 为什么需要它：多个页面 / 弹窗各自读写 document.body.style.overflow 时，
 * 路由切换会让「上锁」「存前值」「卸载清理」的时序交错（卸载钩子是 post-flush，
 * 晚于新页面挂载），导致 hidden 残留或锁被误清。这里改成计数语义：
 * lock/unlock 必须配对，计数归零才真正恢复滚动，谁也不再保存/恢复「前值」。
 *
 * 注意：全局样式里 html 是 overflow-y: scroll，视口滚动条常驻、宽度不随
 * 上锁变化，因此这里刻意不做滚动条宽度补偿——补偿反而会让内容左右跳。
 */
import { unref, watch, onUnmounted } from 'vue'

let lockCount = 0

export function lockBodyScroll() {
  if (lockCount === 0) {
    document.body.style.overflow = 'hidden'
  }
  lockCount++
}

export function unlockBodyScroll() {
  if (lockCount === 0) return
  lockCount--
  if (lockCount === 0) {
    document.body.style.overflow = ''
  }
}

/**
 * 在组件 setup 中把一个布尔源（ref / getter）绑定到滚动锁：
 * 源为真时持锁，为假时释放；组件卸载时若仍持锁会自动释放。
 * 持锁状态内部去重，重复触发不会重复加锁。
 */
export function useBodyScrollLock(source) {
  let held = false
  const apply = (value) => {
    const need = Boolean(unref(value))
    if (need === held) return
    held = need
    if (need) lockBodyScroll()
    else unlockBodyScroll()
  }
  watch(source, apply, { immediate: true })
  onUnmounted(() => {
    if (!held) return
    held = false
    unlockBodyScroll()
  })
}
