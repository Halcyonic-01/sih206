import { Button } from 'antd'
import { Link } from 'react-router-dom'
import { ErrorState } from '@/components/states'

export default function NotFoundPage() {
  return <ErrorState status={404} title="Page not found"
                     detail={<><p>The address may be wrong, or the page may have moved.</p><Link to="/"><Button type="primary">Back to start</Button></Link></>} />
}
