import { Link } from 'react-router-dom'
import { Brand } from './Logo'

export function PortalIdentity() {
  return <div className="portal-identity">
    <Link to="/" aria-label="Pramaan home"><Brand compact size={48} /></Link>
    <div className="portal-descriptor">
      <span className="portal-descriptor__title">AICTE Security Deposit / FDR Portal</span>
    </div>
  </div>
}

export function PortalFooter() {
  return <footer className="portal-footer">
    <div><Brand size={32} /></div>
    <p>AICTE Security Deposit / FDR Portal — Prototype. Not an official AICTE service or endorsement.</p>
    <p>Acceptance is for tracking. Document review and simulated matches do not establish bank authenticity.</p>
  </footer>
}
