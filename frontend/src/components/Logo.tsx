/** User-supplied artwork, kept intact with its original name, tagline and proportions. */
const LOGO = '/pramaan-logo.png'
const ASPECT = 833 / 292

export function LogoMark({ size = 36, title }: { size?: number; inverse?: boolean; title?: string }) {
  return (
    <img src={LOGO} width={Math.round(size * ASPECT)} height={size} alt={title ?? ''}
      aria-hidden={title ? undefined : true} className="logo-mark brand-image" />
  )
}

/** Shared wordmark. Legacy sizing props stay compatible; artwork is never recoloured or cropped. */
export function Brand({ size = 36 }: { inverse?: boolean; compact?: boolean; size?: number }) {
  const width = size * 5
  return (
    <span className="brand-lockup">
      <img src={LOGO} width={width} height={Math.round(width / ASPECT)}
        alt="Pramaan — Trust backed by evidence" className="brand-image" />
    </span>
  )
}
