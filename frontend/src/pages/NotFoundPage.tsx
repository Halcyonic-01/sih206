import { t as tr, useLanguage } from '@/i18n';
import { Button } from 'antd'
import { Link } from 'react-router-dom'
import { ErrorState } from '@/components/states'

export default function NotFoundPage() {
  useLanguage();
  return <ErrorState status={404} title={tr("Page not found")}
                     detail={<><p>{tr("The address may be wrong, or the page may have moved.")}</p><Link to="/"><Button type="primary">{tr("Back to start")}</Button></Link></>} />
}
