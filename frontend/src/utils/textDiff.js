/**
 * 轻量文本 diff 工具，面向中文公众号文案。
 *
 * 思路：先按「句子」做 LCS 对齐拿到锚点（句子精确匹配），
 * 对锚点之间未匹配的句子块再做字符级 LCS diff，得到细粒度的增删。
 * 这样在大段重写时差异块也被切小，不会让 DP 表爆炸。
 *
 * 输出统一为 [{ type: 'equal'|'insert'|'delete', text }] 的操作序列。
 */

// 字符级 DP 规模上限（约 4000×4000，对应 ~64MB Int32Array）。
const CHAR_DP_LIMIT = 16_000_000

// 把文本切成句子片段（保留分隔符与换行，便于无损还原）。
function splitSentences(text) {
  if (!text) return []
  // 在句末标点 / 换行后断开，分隔符归属前一句
  const parts = text.split(/(?<=[。！？；…\n!?;])/)
  return parts.filter((s) => s.length > 0)
}

// 字符级 LCS diff，返回操作序列。带规模保护：过大时整块替换。
function diffChars(a, b) {
  if (a === b) return a ? [{ type: 'equal', text: a }] : []
  if (!a) return b ? [{ type: 'insert', text: b }] : []
  if (!b) return a ? [{ type: 'delete', text: a }] : []

  const n = a.length
  const m = b.length

  if ((n + 1) * (m + 1) > CHAR_DP_LIMIT) {
    return [
      { type: 'delete', text: a },
      { type: 'insert', text: b },
    ]
  }

  const w = m + 1
  const dp = new Int32Array((n + 1) * w)
  for (let i = n - 1; i >= 0; i--) {
    const ai = a[i]
    const row = i * w
    const nextRow = (i + 1) * w
    for (let j = m - 1; j >= 0; j--) {
      if (ai === b[j]) {
        dp[row + j] = dp[nextRow + j + 1] + 1
      } else {
        const down = dp[nextRow + j]
        const right = dp[row + j + 1]
        dp[row + j] = down >= right ? down : right
      }
    }
  }

  const ops = []
  let i = 0
  let j = 0
  const push = (type, ch) => {
    const last = ops[ops.length - 1]
    if (last && last.type === type) last.text += ch
    else ops.push({ type, text: ch })
  }
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      push('equal', a[i]); i++; j++
    } else if (dp[(i + 1) * w + j] >= dp[i * w + j + 1]) {
      push('delete', a[i]); i++
    } else {
      push('insert', b[j]); j++
    }
  }
  while (i < n) { push('delete', a[i]); i++ }
  while (j < m) { push('insert', b[j]); j++ }
  return ops
}

// 片段级 LCS，返回匹配的 (ai, bi) 锚点对
function lcsSegmentAnchors(aSegs, bSegs) {
  const n = aSegs.length
  const m = bSegs.length
  if (n === 0 || m === 0) return []
  const w = m + 1
  const dp = new Int32Array((n + 1) * w)
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      // 仅当片段完全一致且包含非空白内容时才作为锚点
      if (aSegs[i] === bSegs[j] && aSegs[i].trim()) {
        dp[i * w + j] = dp[(i + 1) * w + j + 1] + 1
      } else {
        const down = dp[(i + 1) * w + j]
        const right = dp[i * w + j + 1]
        dp[i * w + j] = down >= right ? down : right
      }
    }
  }
  const anchors = []
  let i = 0
  let j = 0
  while (i < n && j < m) {
    if (aSegs[i] === bSegs[j] && aSegs[i].trim()) {
      anchors.push([i, j]); i++; j++
    } else if (dp[(i + 1) * w + j] >= dp[i * w + j + 1]) {
      i++
    } else {
      j++
    }
  }
  return anchors
}

// 合并相邻同类型操作
function pushOp(ops, type, text) {
  if (!text) return
  const last = ops[ops.length - 1]
  if (last && last.type === type) last.text += text
  else ops.push({ type, text })
}

// 去碎片：把夹在增删之间、长度很短的 equal「孤岛」并入改写，
// 避免「的/了/是」等单字到处零散匹配导致视觉破碎。
function mergeTinyIslands(ops) {
  const ISLAND_MAX = 1 // 去掉空白后不超过 1 字的 equal 视为孤岛
  const out = []
  for (let k = 0; k < ops.length; k++) {
    const op = ops[k]
    const prev = out[out.length - 1]
    const next = ops[k + 1]
    const isIsland =
      op.type === 'equal' &&
      op.text.replace(/\s/g, '').length <= ISLAND_MAX &&
      !op.text.includes('\n') &&
      prev && prev.type !== 'equal' &&
      next && next.type !== 'equal'
    if (isIsland) {
      // 拆成 delete + insert，保持文本完整、颜色连贯
      pushOp(out, 'delete', op.text)
      pushOp(out, 'insert', op.text)
    } else {
      pushOp(out, op.type, op.text)
    }
  }
  return out
}

/**
 * 计算原文 → 润色后文本的 diff 操作序列。
 * @returns {Array<{type:'equal'|'insert'|'delete', text:string}>}
 */
export function diffText(original, polished) {
  const a = original || ''
  const b = polished || ''
  if (a === b) return a ? [{ type: 'equal', text: a }] : []

  const aSegs = splitSentences(a)
  const bSegs = splitSentences(b)
  const anchors = lcsSegmentAnchors(aSegs, bSegs)

  const ops = []
  let ai = 0
  let bi = 0
  const flushGap = (aEnd, bEnd) => {
    const aBlock = aSegs.slice(ai, aEnd).join('')
    const bBlock = bSegs.slice(bi, bEnd).join('')
    if (aBlock || bBlock) {
      for (const op of diffChars(aBlock, bBlock)) pushOp(ops, op.type, op.text)
    }
  }

  for (const [aIdx, bIdx] of anchors) {
    flushGap(aIdx, bIdx)
    pushOp(ops, 'equal', aSegs[aIdx]) // 锚点句完全相等
    ai = aIdx + 1
    bi = bIdx + 1
  }
  flushGap(aSegs.length, bSegs.length)

  return mergeTinyIslands(ops)
}
