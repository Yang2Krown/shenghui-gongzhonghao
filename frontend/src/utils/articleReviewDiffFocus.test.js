import { describe, expect, it } from 'vitest'
import { focusArticleReviewDiff } from './articleReviewDiffFocus'

describe('focusArticleReviewDiff', () => {
  it('保留真正变化并折叠相同或仅有轻微措辞差异的尾部', () => {
    const before = [
      '接下来把整个过程放出来，也请大家一起锐评一下。',
      '对于设计，我和朋友都算外行。',
      '因为这个品牌本来就是饭桌上临时想的，我自己也没有多成熟的方向。',
      'Miora倒是没有急着给我硬画，它识别到了这个需求是模糊的，就给了我一些选项，引导我去定品牌的调性和logo风格。',
      '几分钟后，画布上铺开了好几版。',
    ].join('\n')
    const after = [
      '先给大家看一眼最终效果，后面还有宣传视频之类的。',
      '接下来把整个过程放出来。',
      '因为这个品牌本来就是临时起意的，我自己也没有多成熟的方向。',
      'Miora有个很好的点是，它识别到了这个需求是模糊的，就给了我一些选项，引导我去定品牌的调性和logo风格。',
      '几分钟后，画布上铺开了好几版。',
    ].join('\n')

    const result = focusArticleReviewDiff(before, after)

    expect(result.hasOmitted).toBe(true)
    expect(result.omittedUnits).toBeGreaterThanOrEqual(3)
    expect(result.before).toContain('锐评一下')
    expect(result.after).toContain('最终效果')
    expect(result.before).not.toContain('品牌本来就是饭桌上临时想的')
    expect(result.after).not.toContain('品牌本来就是临时起意的')
  })

  it('数字或关键英文标识发生变化时不折叠', () => {
    const result = focusArticleReviewDiff(
      '转化率从10%提升到20%。\n后续流程保持不变。',
      '转化率从10%提升到30%。\n后续流程保持不变。',
    )

    expect(result.hasOmitted).toBe(true)
    expect(result.before).toContain('20%')
    expect(result.after).toContain('30%')
    expect(result.before).not.toContain('后续流程保持不变')
  })

  it('只有轻微措辞时保留完整内容，避免卡片变成空白', () => {
    const before = '我们要做的事情。'
    const after = '我们要做了事情！'
    const result = focusArticleReviewDiff(before, after)

    expect(result.hasOmitted).toBe(false)
    expect(result.before).toBe(before)
    expect(result.after).toBe(after)
  })
})
