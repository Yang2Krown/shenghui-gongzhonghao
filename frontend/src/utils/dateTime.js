const BJT_TIME_ZONE = 'Asia/Shanghai'
const NAIVE_DATE_TIME_RE = /^(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?:[T\s](\d{1,2})(?::(\d{2}))?(?::\d{2}(?:\.\d+)?)?)?/
const OFFSET_SUFFIX_RE = /(?:Z|[+-]\d{2}:?\d{2})$/i

const padHour = (value) => String(value || 0).padStart(2, '0')

const formatParts = (date) => {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: BJT_TIME_ZONE,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const valueOf = (type) => parts.find((part) => part.type === type)?.value || ''
  return `${valueOf('year')}/${valueOf('month')}/${valueOf('day')} ${padHour(valueOf('hour'))}:${valueOf('minute')}`
}

/**
 * Format API timestamps as Beijing time without locale punctuation.
 * The API historically returns naive Beijing timestamps, while a few
 * endpoints may return an explicit ISO offset; both forms are supported.
 */
export const formatDateTimeMinute = (value, fallback = '—') => {
  if (!value) return fallback
  const source = String(value).trim()
  if (!source) return fallback

  const naiveMatch = source.match(NAIVE_DATE_TIME_RE)
  if (naiveMatch && !OFFSET_SUFFIX_RE.test(source)) {
    const [, year, month, day, hour = '0', minute = '00'] = naiveMatch
    return `${year}/${Number(month)}/${Number(day)} ${padHour(hour)}:${String(minute).padStart(2, '0')}`
  }

  const date = new Date(source)
  return Number.isNaN(date.getTime()) ? fallback : formatParts(date)
}
