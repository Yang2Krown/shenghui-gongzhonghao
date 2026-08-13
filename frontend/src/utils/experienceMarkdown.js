import { marked, Renderer } from 'marked'

const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
}[character]))

const isSafeUrl = (value) => /^(https?:\/\/|mailto:|\/|#)/i.test(String(value || '').trim())

const renderer = new Renderer()

// Experience content is user/uploaded material. Keep Markdown formatting but
// never pass raw HTML through v-html.
renderer.html = ({ text }) => escapeHtml(text)
renderer.link = function ({ href, title, tokens }) {
  const label = this.parser.parseInline(tokens)
  const safeHref = String(href || '').trim()
  if (!isSafeUrl(safeHref)) return label
  const titleAttribute = title ? ` title="${escapeHtml(title)}"` : ''
  return `<a href="${escapeHtml(safeHref)}"${titleAttribute} target="_blank" rel="noopener noreferrer">${label}</a>`
}
renderer.image = function ({ href, title, text }) {
  const safeHref = String(href || '').trim()
  if (!/^https?:\/\//i.test(safeHref)) return ''
  const titleAttribute = title ? ` title="${escapeHtml(title)}"` : ''
  return `<img src="${escapeHtml(safeHref)}" alt="${escapeHtml(text)}"${titleAttribute} loading="lazy">`
}

export const renderExperienceMarkdown = (value) => {
  const source = String(value || '')
  if (!source.trim()) return ''
  return marked.parse(source, {
    breaks: true,
    gfm: true,
    renderer,
  })
}
