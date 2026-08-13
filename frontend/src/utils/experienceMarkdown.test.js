import { describe, expect, it } from 'vitest'
import { renderExperienceMarkdown } from './experienceMarkdown'

describe('renderExperienceMarkdown', () => {
  it('renders common Markdown blocks for the complete experience view', () => {
    const html = renderExperienceMarkdown('# 方法论\n\n**先说结论**\n\n- 第一步\n- 第二步\n\n> 保留证据')

    expect(html).toContain('<h1>方法论</h1>')
    expect(html).toContain('<strong>先说结论</strong>')
    expect(html).toContain('<li>第一步</li>')
    expect(html).toContain('<blockquote>')
  })

  it('escapes raw HTML and removes unsafe links while keeping safe links', () => {
    const html = renderExperienceMarkdown('<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n[文档](https://example.com)')

    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
    expect(html).not.toContain('<script>')
    expect(html).not.toContain('javascript:')
    expect(html).toContain('href="https://example.com"')
    expect(html).toContain('rel="noopener noreferrer"')
  })

  it('returns an empty string for empty content', () => {
    expect(renderExperienceMarkdown('')).toBe('')
    expect(renderExperienceMarkdown(null)).toBe('')
  })
})
