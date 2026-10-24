import dayjs from 'dayjs'

export const time = (value: string) => dayjs(value).format('D MMM YYYY, HH:mm:ss')

/** Readable single-line value for the before/after table. React escapes it; nothing is rendered as HTML. */
export function show(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'string') return value
  return JSON.stringify(value)
}

/** Date-range picker values -> the API's inclusive YYYY-MM-DD filters. */
export function rangeFilters(range: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null | undefined) {
  return {
    date_from: range?.[0]?.format('YYYY-MM-DD'),
    date_to: range?.[1]?.format('YYYY-MM-DD'),
  }
}
