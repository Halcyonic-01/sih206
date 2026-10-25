import { colors } from '@/theme'

/**
 * The Pramaan mark: a shield (protection of the deposit) holding a check (evidence), under a saffron band.
 * It is an original mark for this portal, not the AICTE or national emblem.
 */
export function LogoMark({ size = 36, inverse = false, title }: { size?: number; inverse?: boolean; title?: string }) {
  const body = inverse ? '#ffffff' : colors.primary
  const check = inverse ? colors.navy : '#ffffff'
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" role={title ? 'img' : undefined} aria-label={title}
         aria-hidden={title ? undefined : true} focusable="false" className="logo-mark">
      <path d="M20 2.5 34.5 8v11.2c0 8.6-5.7 14.9-14.5 18.3C11.2 34.1 5.5 27.8 5.5 19.2V8L20 2.5Z" fill={body} />
      <path d="M5.5 8 20 2.5 34.5 8v4.6L20 7.2 5.5 12.6V8Z" fill={colors.accent} />
      <path d="m12.8 21.4 5.2 5.2 9.4-10.8" fill="none" stroke={check} strokeWidth="3.4" strokeLinecap="round"
            strokeLinejoin="round" />
    </svg>
  )
}

/** Mark with the product name. `compact` drops the descriptor line (header on small screens). */
export function Brand({ inverse = false, compact = false, size = 36 }: { inverse?: boolean; compact?: boolean; size?: number }) {
  return (
    <span className={`brand-lockup${inverse ? ' brand-lockup--inverse' : ''}`}>
      <LogoMark size={size} inverse={inverse} />
      <span className="brand-text">
        <strong className="brand-name">Pramaan</strong>
        {!compact && <span className="brand-sub">AICTE Deposit Portal</span>}
      </span>
    </span>
  )
}
