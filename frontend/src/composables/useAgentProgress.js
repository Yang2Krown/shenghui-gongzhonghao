/**
 * useAgentProgress — SSE 驱动的 Agent 进度 composable
 *
 * 进度曲线：0→30% 快 → 75% 慢 → 95% 更慢 → 99.50% 卡住
 * Agent 切换：上一个冲到 100% → 停 1.5s → 下一个从 0% 开始（不回跳）
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
  let _rushing = false       // 正在冲刺到 100%
  let _pendingStep = null    // 冲刺完成后待切换的 step 数据 { idx, agent, action }

  // ── 启动 SSE 连接 ─────────────────────────────────
  function start(sseUrl) {
    stop()

    isRunning.value = true
    result.value = null
    error.value = null
    currentStepIndex.value = -1
    stepPercent.value = 0

    const token = localStorage.getItem('token') || ''
    const urlWithToken = sseUrl + (sseUrl.includes('?') ? '&' : '?') + `token=${token}`

    _es = new EventSource(urlWithToken)

    // ── step_start ──
    _es.addEventListener('step_start', (e) => {
      const data = JSON.parse(e.data)
      const idx = data.step - 1

      // 确保 steps 数组够长
      while (steps.value.length <= idx) {
        steps.value.push({ agent: `Agent ${steps.value.length + 1}`, action: '' })
      }

      // 更新步骤元信息（文字描述），但不切换 currentStepIndex
      steps.value[idx] = {
        agent: data.agent,
        action: data.action || '',
        avatar: data.avatar || '',
      }

      // 如果正在冲刺上一个 Agent，记下来等冲刺完再切
      if (_rushing) {
        // 只允许向前推进（更高 index），防止再生/快速步骤覆盖
        if (_pendingStep === null || idx > _pendingStep.idx) {
          _pendingStep = { idx }
        }
      } else {
        // 没在冲刺，直接延迟切换
        _switchToStep(idx)
      }
    })

    // ── step_done ──
    _es.addEventListener('step_done', (e) => {
      _rushToFull()
    })

    // ── complete ──
    _es.addEventListener('complete', (e) => {
      _rushToFull()
    })

    // ── result ──
    _es.addEventListener('result', (e) => {
      const data = JSON.parse(e.data)
      result.value = data
      isRunning.value = false
      if (_es) {
        _es.close()
        _es = null
      }
    })

    // ── error ──
    _es.addEventListener('error', (e) => {
      if (e.type === 'error' && !_es) return

      if (e.data) {
        try {
          const data = JSON.parse(e.data)
          error.value = data.message || '未知错误'
        } catch {
          error.value = '连接异常'
        }
      } else {
        error.value = '连接断开'
      }

      _stopAll()
      isRunning.value = false
      if (_es) {
        _es.close()
        _es = null
      }
    })
  }

  // ── 停止 ──────────────────────────────────────────
  function stop() {
    _stopAll()
    if (_es) {
      _es.close()
      _es = null
    }
    isRunning.value = false
  }

  // ── 切换到新步骤（延迟后调用，此时上一个已完成 100%） ──
  function _switchToStep(idx) {
    // 延迟 1.5s，让用户看到上一个 Agent 停在 100%
    _stepTimer = setTimeout(() => {
      _stepTimer = null
      currentStepIndex.value = idx
      stepPercent.value = 0
      _startSmoothProgress()
    }, 1500)
  }

  // ── 平滑进度动画 ──────────────────────────────────
  // 0→30% 快 | 30→75% 慢 | 75→95% 更慢 | 95→99.50% 极慢后卡住
  function _startSmoothProgress() {
    _stopAll()
    stepPercent.value = 0

    const TICK = 200

    _stepTimer = setInterval(() => {
      const cur = stepPercent.value

      if (cur < 30) {
        // 快速起步
        stepPercent.value = Math.min(cur + 1.8, 30)
      } else if (cur < 75) {
        // 慢速
        const remaining = 75 - cur
        stepPercent.value = Math.min(cur + Math.max(0.3, remaining * 0.04), 75)
      } else if (cur < 95) {
        // 更慢
        const remaining = 95 - cur
        stepPercent.value = Math.min(cur + Math.max(0.1, remaining * 0.02), 95)
      } else if (cur < 99.50) {
        // 极慢，逐渐卡住
        const remaining = 99.50 - cur
        stepPercent.value = Math.min(cur + Math.max(0.02, remaining * 0.01), 99.50)
      }
      // 到 99.50% 后不再增长，等 step_done
    }, TICK)
  }

  // ── 冲刺到 100%（step_done 时调用，~1s） ──
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

        // 冲刺完成，如果有下一个 Agent 在等，延迟切换
        if (_pendingStep) {
          const next = _pendingStep
          _pendingStep = null
          _switchToStep(next.idx)
        }
        return
      }
      // ease-out ~1s
      const remaining = 100 - cur
      stepPercent.value = Math.min(cur + Math.max(1, remaining * 0.12), 100)
    }, TICK)
  }

  // ── 清理所有定时器 ──
  function _stopAll() {
    if (_stepTimer) {
      clearInterval(_stepTimer)
      clearTimeout(_stepTimer)  // 兼顾 timeout 和 interval
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
