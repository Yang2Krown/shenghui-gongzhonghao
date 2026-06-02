/**
 * useAgentProgress — SSE 驱动的 Agent 进度 composable
 *
 * 事件先入队，再按固定间隔逐个处理：即使代理层偶尔把多条事件一次性吐出，
 * 前端依然能播放出完整的步骤切换 + 进度条动画。
 *
 * 状态机刻意做得简单、抗乱序：
 *   - 收到 step_start：立即切到该步、进度归零、开始平滑爬升（不延迟、不排队，
 *     避免后续事件打断切换导致"步骤闪过/进度条卡住"）。
 *   - 收到 step_done / complete：停止爬升、把当前步推满（靠 CSS 过渡平滑到 100%）。
 *   - 收到 result / error：结束。
 */

import { ref, computed } from 'vue'

export function useAgentProgress() {
  // ── 状态 ──────────────────────────────────────────
  const steps = ref([])
  const currentStepIndex = ref(-1)
  const stepPercent = ref(0)
  const result = ref(null)
  const error = ref(null)
  const isRunning = ref(false)

  let _es = null
  let _climbTimer = null

  // ── 事件队列（应对代理把多条事件一次性吐出的情况） ──
  let _eventQueue = []
  let _drainTimer = null
  const DRAIN_INTERVAL = 400

  function _enqueue(handler) {
    _eventQueue.push(handler)
    if (!_drainTimer) {
      _drainNext()
    }
  }

  function _drainNext() {
    if (_eventQueue.length === 0) {
      _drainTimer = null
      return
    }
    const handler = _eventQueue.shift()
    handler()
    _drainTimer = setTimeout(_drainNext, DRAIN_INTERVAL)
  }

  function _flushQueue() {
    if (_drainTimer) {
      clearTimeout(_drainTimer)
      _drainTimer = null
    }
    _eventQueue = []
  }

  // ── 启动 SSE 连接 ─────────────────────────────────
  function start(sseUrl) {
    stop()

    isRunning.value = true
    result.value = null
    error.value = null
    steps.value = []
    currentStepIndex.value = -1
    stepPercent.value = 0

    const token = localStorage.getItem('token') || ''
    const urlWithToken = sseUrl + (sseUrl.includes('?') ? '&' : '?') + `token=${token}`

    _es = new EventSource(urlWithToken)

    _es.addEventListener('step_start', (e) => {
      const data = JSON.parse(e.data)
      _enqueue(() => _handleStepStart(data))
    })

    _es.addEventListener('step_done', () => {
      _enqueue(() => _handleStepDone())
    })

    _es.addEventListener('complete', () => {
      _enqueue(() => _handleStepDone())
    })

    _es.addEventListener('result', (e) => {
      const data = JSON.parse(e.data)
      _enqueue(() => {
        // 收尾：把当前步推满，标记结束
        _stopClimb()
        stepPercent.value = 100
        result.value = data
        isRunning.value = false
      })
      if (_es) {
        _es.close()
        _es = null
      }
    })

    _es.addEventListener('error', (e) => {
      if (e.type === 'error' && !_es) return

      let msg = '连接断开'
      if (e.data) {
        try {
          const data = JSON.parse(e.data)
          msg = data.message || '未知错误'
        } catch {
          msg = '连接异常'
        }
      }

      _flushQueue()
      _stopClimb()
      error.value = msg
      isRunning.value = false
      if (_es) {
        _es.close()
        _es = null
      }
    })
  }

  // ── 事件处理 ──────────────────────────────────────
  function _handleStepStart(data) {
    const idx = data.step - 1

    // 补齐占位，保证 steps[idx] 可写
    while (steps.value.length <= idx) {
      steps.value.push({ agent: `Agent ${steps.value.length + 1}`, action: '' })
    }

    steps.value[idx] = {
      agent: data.agent,
      action: data.action || '',
      avatar: data.avatar || '',
    }

    // 立即切到该步并开始爬升（不延迟、不排队）
    currentStepIndex.value = idx
    stepPercent.value = 0
    _startSmoothProgress()
  }

  function _handleStepDone() {
    // 当前步骤完成：停止爬升，推满到 100%（CSS 过渡会平滑这一跳）
    _stopClimb()
    stepPercent.value = 100
  }

  // ── 平滑进度动画：在 step_start 到 step_done 之间缓慢爬到 95% ──
  function _startSmoothProgress() {
    _stopClimb()
    stepPercent.value = 0

    const TICK = 150
    _climbTimer = setInterval(() => {
      const cur = stepPercent.value
      if (cur < 30) {
        stepPercent.value = Math.min(cur + 2.5, 30)
      } else if (cur < 70) {
        const remaining = 70 - cur
        stepPercent.value = Math.min(cur + Math.max(0.5, remaining * 0.06), 70)
      } else if (cur < 95) {
        const remaining = 95 - cur
        stepPercent.value = Math.min(cur + Math.max(0.15, remaining * 0.03), 95)
      }
      // 95% 之后停住，等 step_done 推满，避免"卡在 99% 又不结束"的观感
    }, TICK)
  }

  // ── 停止 ──────────────────────────────────────────
  function stop() {
    _flushQueue()
    _stopClimb()
    if (_es) {
      _es.close()
      _es = null
    }
    isRunning.value = false
  }

  function _stopClimb() {
    if (_climbTimer) {
      clearInterval(_climbTimer)
      _climbTimer = null
    }
  }

  // ── 计算属性 ──────────────────────────────────────
  const overallPercent = computed(() => {
    if (steps.value.length === 0) return 0
    const completedSteps = currentStepIndex.value
    if (completedSteps < 0) return 0
    const currentProgress = stepPercent.value / 100
    return Math.min(((completedSteps + currentProgress) / steps.value.length) * 100, 100)
  })

  return {
    steps,
    currentStepIndex,
    stepPercent,
    overallPercent,
    result,
    error,
    isRunning,
    start,
    stop,
  }
}
