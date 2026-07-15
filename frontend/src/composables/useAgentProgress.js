/**
 * useAgentProgress — Agent 进度 composable（轮询实现）
 *
 * 通过轮询通用进度接口 `/progress/{run_id}` 获取任务快照。
 *
 * 每次 step 切换时：当前步先补满到 100%（1s 动画）→ 停顿 0.5s → 归零 → 下一步开始。
 */

import { ref, computed } from 'vue'
import { get } from '@/api/api'

const POLL_INTERVAL = 1500
const ANIM_100_MS = 1000     // 补满到 100% 动画时长
const ANIM_100_PAUSE = 500   // 到 100% 后停留时间

export function useAgentProgress() {
  // ── 状态 ──────────────────────────────────────────
  const steps = ref([])
  const currentStepIndex = ref(-1)
  const stepPercent = ref(0)
  const noStepTransition = ref(false)  // true = 禁用进度条 CSS transition（归零瞬间用）
  const result = ref(null)
  const error = ref(null)
  const isRunning = ref(false)

  let _pollTimer = null
  let _climbTimer = null
  let _advanceTimer = null

  // ── 启动（直接传入 runId）──
  function start(runId) {
    stop()

    isRunning.value = true
    result.value = null
    error.value = null
    steps.value = []
    currentStepIndex.value = -1
    stepPercent.value = 0

    runId = String(runId || '').trim()
    if (!runId) {
      isRunning.value = false
      return
    }

    _poll(runId)
    _pollTimer = setInterval(() => _poll(runId), POLL_INTERVAL)
  }

  async function _poll(runId) {
    try {
      const res = await get(`/progress/${runId}`)
      const d = res?.data || {}
      if (d.exists === false) return
      _applySnapshot(d)
    } catch {
      // 单次失败忽略
    }
  }

  function _applySnapshot(d) {
    if (Array.isArray(d.steps) && d.steps.length) {
      steps.value = d.steps.map((s) => ({
        step: s.step,
        agent: s.agent,
        action: s.action || '',
        avatar: s.avatar || '',
      }))
    }

    // 按步骤号在数组里找真实位置，容错步骤号断层/0 基/缺省（如正文跳过 Agent E 后是 0,1,2,3,5）。
    // 找不到时回退到旧的「current_step - 1」逻辑。
    let curIdx = steps.value.findIndex((s) => s.step === d.current_step)
    if (curIdx < 0) curIdx = (d.current_step || 0) - 1
    if (curIdx >= 0 && curIdx !== currentStepIndex.value) {
      if (currentStepIndex.value < 0) {
        // 首步直接出现，不触发补满-归零动画
        currentStepIndex.value = curIdx
        stepPercent.value = 0
        _startClimb()
      } else {
        // 后续步切换：先补满上一步到 100%，停顿后再归零开始新步
        _advanceStep(curIdx)
      }
    }

    // 只在任务真正结束（done）后才展示 error，避免中间重试的错误事件导致进度条卡死
    if (d.done && d.error) {
      _stopClimb()
      _stopPoll()
      error.value = d.error
      isRunning.value = false
      return
    }

    if (d.done && d.result) {
      _stopPoll()          // 立即停轮询（不要等 _finishStep 的 delay）
      _finishStep()
      result.value = d.result
    }
  }

  // ── 步切换动画：补满 100% → 停顿 → 切到新步 → 瞬间归零 → 开始爬 ──
  function _advanceStep(newIdx) {
    _stopClimb()
    // 如果上一轮 advance 动画还在跑，先清掉（避免多次触发叠加）
    if (_advanceTimer) {
      clearTimeout(_advanceTimer)
      _advanceTimer = null
    }

    // 冲到 100% 触发 CSS transition
    if (stepPercent.value < 100) {
      stepPercent.value = 100
    }

    // 等动画 + 停顿后切换
    _advanceTimer = setTimeout(() => {
      _advanceTimer = null
      currentStepIndex.value = newIdx
      // 瞬间归零：禁用过渡 → 归零 → 下一帧恢复过渡
      noStepTransition.value = true
      stepPercent.value = 0
      requestAnimationFrame(() => {
        noStepTransition.value = false
        _startClimb()
      })
    }, ANIM_100_MS + ANIM_100_PAUSE)
  }

  // ── 完成动画：补满 100% 并停顿 ──
  function _finishStep() {
    _stopClimb()
    stepPercent.value = 100
    // 停顿后再标记完成（由外部决定如何显示结果）
    _advanceTimer = setTimeout(() => {
      isRunning.value = false
    }, ANIM_100_MS + ANIM_100_PAUSE)
  }

  // ── 平滑进度：在两次轮询之间让当前步缓慢爬到 95% ──
  function _startClimb() {
    _stopClimb()
    _climbTimer = setInterval(() => {
      const cur = stepPercent.value
      if (cur < 30) {
        stepPercent.value = Math.min(cur + 2, 30)
      } else if (cur < 70) {
        stepPercent.value = Math.min(cur + Math.max(0.4, (70 - cur) * 0.05), 70)
      } else if (cur < 95) {
        stepPercent.value = Math.min(cur + Math.max(0.1, (95 - cur) * 0.02), 95)
      }
    }, 200)
  }

  function _stopClimb() {
    if (_climbTimer) {
      clearInterval(_climbTimer)
      _climbTimer = null
    }
  }

  function _stopPoll() {
    if (_pollTimer) {
      clearInterval(_pollTimer)
      _pollTimer = null
    }
  }

  function stop() {
    _stopPoll()
    _stopClimb()
    if (_advanceTimer) {
      clearTimeout(_advanceTimer)
      _advanceTimer = null
    }
    isRunning.value = false
  }

  /** 重置所有状态，准备接受新 run 的快照 */
  function reset() {
    _stopPoll()
    _stopClimb()
    if (_advanceTimer) {
      clearTimeout(_advanceTimer)
      _advanceTimer = null
    }
    steps.value = []
    currentStepIndex.value = -1
    stepPercent.value = 0
    noStepTransition.value = false
    result.value = null
    error.value = null
    isRunning.value = false
  }

  /** 外部直接喂快照（挖掘页用自己的轮询，不走 start() 的定时器） */
  function applySnapshot(d) {
    _applySnapshot(d)
  }

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
    noStepTransition,
    overallPercent,
    result,
    error,
    isRunning,
    start,
    stop,
    reset,
    applySnapshot,
  }
}
