/**
 * useAgentProgress — SSE 驱动的 Agent 进度 composable
 *
 * 所有 SSE 事件先入队，再按固定间隔逐个处理。
 * 这样即使代理层把整个响应缓冲到最后才交付（事件同时到达），
 * 前端依然能播放完整的步骤切换 + 进度条动画。
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
  let _stepTimer = null
  let _rushing = false
  let _pendingStep = null

  // ── 事件队列（解决代理缓冲导致事件同时到达的问题） ──
  let _eventQueue = []
  let _drainTimer = null
  const DRAIN_INTERVAL = 600

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

    _es.addEventListener('step_done', (e) => {
      _enqueue(() => _handleStepDone())
    })

    _es.addEventListener('complete', (e) => {
      _enqueue(() => _handleStepDone())
    })

    _es.addEventListener('result', (e) => {
      const data = JSON.parse(e.data)
      _enqueue(() => {
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
      _stopAll()
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

    while (steps.value.length <= idx) {
      steps.value.push({ agent: `Agent ${steps.value.length + 1}`, action: '' })
    }

    steps.value[idx] = {
      agent: data.agent,
      action: data.action || '',
      avatar: data.avatar || '',
    }

    if (_rushing) {
      if (_pendingStep === null || idx > _pendingStep.idx) {
        _pendingStep = { idx }
      }
    } else if (currentStepIndex.value < 0) {
      currentStepIndex.value = idx
      stepPercent.value = 0
      _startSmoothProgress()
    } else {
      _switchToStep(idx)
    }
  }

  function _handleStepDone() {
    _rushToFull()
  }

  // ── 停止 ──────────────────────────────────────────
  function stop() {
    _flushQueue()
    _stopAll()
    if (_es) {
      _es.close()
      _es = null
    }
    isRunning.value = false
  }

  // ── 切换到新步骤 ──
  function _switchToStep(idx) {
    _stepTimer = setTimeout(() => {
      _stepTimer = null
      currentStepIndex.value = idx
      stepPercent.value = 0
      _startSmoothProgress()
    }, 800)
  }

  // ── 平滑进度动画 ──
  function _startSmoothProgress() {
    _stopAll()
    stepPercent.value = 0

    const TICK = 150

    _stepTimer = setInterval(() => {
      const cur = stepPercent.value

      if (cur < 30) {
        stepPercent.value = Math.min(cur + 2.5, 30)
      } else if (cur < 75) {
        const remaining = 75 - cur
        stepPercent.value = Math.min(cur + Math.max(0.5, remaining * 0.06), 75)
      } else if (cur < 95) {
        const remaining = 95 - cur
        stepPercent.value = Math.min(cur + Math.max(0.2, remaining * 0.03), 95)
      } else if (cur < 99.50) {
        const remaining = 99.50 - cur
        stepPercent.value = Math.min(cur + Math.max(0.05, remaining * 0.015), 99.50)
      }
    }, TICK)
  }

  // ── 冲刺到 100% ──
  function _rushToFull() {
    _stopAll()
    _rushing = true
    _pendingStep = null

    const TICK = 30
    _stepTimer = setInterval(() => {
      const cur = stepPercent.value
      if (cur >= 100) {
        stepPercent.value = 100
        clearInterval(_stepTimer)
        _stepTimer = null
        _rushing = false

        if (_pendingStep) {
          const next = _pendingStep
          _pendingStep = null
          _switchToStep(next.idx)
        }
        return
      }
      const remaining = 100 - cur
      stepPercent.value = Math.min(cur + Math.max(1, remaining * 0.12), 100)
    }, TICK)
  }

  // ── 清理所有定时器 ──
  function _stopAll() {
    if (_stepTimer) {
      clearInterval(_stepTimer)
      clearTimeout(_stepTimer)
      _stepTimer = null
    }
    _rushing = false
    _pendingStep = null
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
