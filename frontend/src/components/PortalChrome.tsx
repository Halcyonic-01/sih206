import { t as tr, useLanguage } from '@/i18n';
import { Link } from 'react-router-dom'
import { Brand } from './Logo'
import { LanguageToggle } from '@/i18n/LanguageToggle';

export function PortalIdentity() {
  useLanguage();
  return <div className="portal-identity">
    <Link to="/" aria-label={tr("Pramaan home")}><Brand compact size={48} /></Link>
    <div className="portal-descriptor">
      <span className="portal-descriptor__title">{tr("AICTE Security Deposit / FDR Portal")}</span>
    </div>
    <LanguageToggle />
  </div>
}

export function PortalFooter() {
  useLanguage();
  return <footer className="portal-footer">
    <div><Brand size={32} /></div>
    <p>{tr("AICTE Security Deposit / FDR Portal — Prototype. Not an official AICTE service or endorsement.")}</p>
    <p>{tr("Acceptance is for tracking. Document review and simulated matches do not establish bank authenticity.")}</p>
  </footer>
}
