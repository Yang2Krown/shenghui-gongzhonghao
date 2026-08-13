const ALIGN_SIMILARITY = 0.56
const COLLAPSE_SIMILARITY = 0.84
const OMITTED_MARKER = '……（基本未变内容已折叠）'

const normalizeText = (value) => String(value || '')
  .normalize('NFKC')
  .toLowerCase()
  .replace(/\s+/g, '')
  .replace(/[，。！？；：、“”‘’（）《》【】…,.!?;:"'()\[\]<>~—_\-]/g, '')
  .replace(/[的了着过地得而且也都就呢吧啊呀哦嘛喽]/g, '')

const materialSignature = (value) => {
  const text = String(value || '').normalize('NFKC').toLowerCase()
  const numbers = text.match(/\d+(?:\.\d+)?%?/g) || []
  const latinTerms = text.match(/[a-z][a-z0-9._-]*/g) || []
  const polarities = text.match(/(?:不|没|未|无)(?:能|会|是|可|要|应|需|支持|允许|存在|包含|提供)/g) || []
  return JSON.stringify([numbers, latinTerms, polarities])
}

const lcsSimilarity = (leftValue, rightValue) => {
  const left = normalizeText(leftValue)
  const right = normalizeText(rightValue)
  if (!left || !right) return 0
  if (left === right) return 1

  let previous = new Uint16Array(right.length + 1)
  let current = new Uint16Array(right.length + 1)
  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      current[rightIndex] = left[leftIndex - 1] === right[rightIndex - 1]
        ? previous[rightIndex - 1] + 1
        : Math.max(previous[rightIndex], current[rightIndex - 1])
    }
    ;[previous, current] = [current, previous]
    current.fill(0)
  }
  return (2 * previous[right.length]) / (left.length + right.length)
}

export const splitChangeUnits = (value) => {
  const text = String(value || '').replace(/\r\n?/g, '\n').trim()
  if (!text) return []
  const units = []
  for (const rawLine of text.split(/\n+/)) {
    const line = rawLine.trim()
    if (!line) continue
    const sentences = line.match(/[^。！？!?；;]+[。！？!?；;]?/g) || [line]
    for (const sentence of sentences) {
      const unit = sentence.trim()
      if (unit) units.push(unit)
    }
  }
  return units
}

const alignUnits = (beforeUnits, afterUnits) => {
  const beforeCount = beforeUnits.length
  const afterCount = afterUnits.length
  const scores = Array.from({ length: beforeCount + 1 }, () => new Float32Array(afterCount + 1))
  const directions = Array.from({ length: beforeCount + 1 }, () => new Uint8Array(afterCount + 1))
  const similarities = Array.from({ length: beforeCount }, () => new Float32Array(afterCount))

  for (let beforeIndex = 1; beforeIndex <= beforeCount; beforeIndex += 1) {
    for (let afterIndex = 1; afterIndex <= afterCount; afterIndex += 1) {
      const similarity = lcsSimilarity(beforeUnits[beforeIndex - 1], afterUnits[afterIndex - 1])
      similarities[beforeIndex - 1][afterIndex - 1] = similarity
      const diagonal = similarity >= ALIGN_SIMILARITY
        ? scores[beforeIndex - 1][afterIndex - 1] + similarity
        : -1
      const beforeOnly = scores[beforeIndex - 1][afterIndex]
      const afterOnly = scores[beforeIndex][afterIndex - 1]
      if (diagonal >= beforeOnly && diagonal >= afterOnly) {
        scores[beforeIndex][afterIndex] = diagonal
        directions[beforeIndex][afterIndex] = 1
      } else if (beforeOnly >= afterOnly) {
        scores[beforeIndex][afterIndex] = beforeOnly
        directions[beforeIndex][afterIndex] = 2
      } else {
        scores[beforeIndex][afterIndex] = afterOnly
        directions[beforeIndex][afterIndex] = 3
      }
    }
  }

  const aligned = []
  let beforeIndex = beforeCount
  let afterIndex = afterCount
  while (beforeIndex > 0 || afterIndex > 0) {
    const direction = directions[beforeIndex]?.[afterIndex]
    if (beforeIndex > 0 && afterIndex > 0 && direction === 1) {
      aligned.push({
        before: beforeUnits[beforeIndex - 1],
        after: afterUnits[afterIndex - 1],
        similarity: similarities[beforeIndex - 1][afterIndex - 1],
      })
      beforeIndex -= 1
      afterIndex -= 1
    } else if (beforeIndex > 0 && (afterIndex === 0 || direction === 2)) {
      aligned.push({ before: beforeUnits[beforeIndex - 1], after: null, similarity: 0 })
      beforeIndex -= 1
    } else {
      aligned.push({ before: null, after: afterUnits[afterIndex - 1], similarity: 0 })
      afterIndex -= 1
    }
  }
  return aligned.reverse()
}

const isCollapsiblePair = (pair) => {
  if (!pair.before || !pair.after || pair.similarity < COLLAPSE_SIMILARITY) return false
  const beforeNormalized = normalizeText(pair.before)
  const afterNormalized = normalizeText(pair.after)
  if (beforeNormalized !== afterNormalized && Math.min(beforeNormalized.length, afterNormalized.length) < 8) return false
  return materialSignature(pair.before) === materialSignature(pair.after)
}

/**
 * 语义块继续作为分析和评论锚点；这里只为卡片生成“实际变化摘录”。
 * 相同或仅有轻微措辞差异的句子会折叠，完整原文仍可由界面展开。
 */
export const focusArticleReviewDiff = (beforeValue, afterValue) => {
  const fullBefore = String(beforeValue || '').trim()
  const fullAfter = String(afterValue || '').trim()
  if (!fullBefore || !fullAfter) {
    return { before: fullBefore, after: fullAfter, fullBefore, fullAfter, omittedUnits: 0, hasOmitted: false }
  }

  const aligned = alignUnits(splitChangeUnits(fullBefore), splitChangeUnits(fullAfter))
  const beforeParts = []
  const afterParts = []
  let omittedUnits = 0
  let materialUnits = 0
  let omissionOpen = false

  for (const pair of aligned) {
    if (isCollapsiblePair(pair)) {
      omittedUnits += 1
      if (!omissionOpen) {
        beforeParts.push(OMITTED_MARKER)
        afterParts.push(OMITTED_MARKER)
        omissionOpen = true
      }
      continue
    }
    omissionOpen = false
    if (pair.before) beforeParts.push(pair.before)
    if (pair.after) afterParts.push(pair.after)
    if (pair.before || pair.after) materialUnits += 1
  }

  if (!omittedUnits || !materialUnits) {
    return { before: fullBefore, after: fullAfter, fullBefore, fullAfter, omittedUnits: 0, hasOmitted: false }
  }
  return {
    before: beforeParts.join('\n'),
    after: afterParts.join('\n'),
    fullBefore,
    fullAfter,
    omittedUnits,
    hasOmitted: true,
  }
}
