import dayjs from 'dayjs'

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', minimumFractionDigits: 2 })

/** Rupee amount in lakh/crore grouping, e.g. 500000.25 -> ₹5,00,000.25. Unparseable input is returned unchanged. */
export function formatInr(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  const number = typeof value === 'number' ? value : Number(value)
  return Number.isFinite(number) ? inr.format(number) : String(value)
}

/** Integer paise (the API's money unit) as rupees. */
export function formatPaise(paise: number | string | null | undefined): string {
  if (paise === null || paise === undefined || paise === '') return '—'
  const number = Number(paise)
  return Number.isFinite(number) ? inr.format(number / 100) : '—'
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('D MMM YYYY') : value
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('D MMM YYYY, HH:mm') : value
}
