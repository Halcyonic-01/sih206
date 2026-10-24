import { Button } from 'antd'
import { Link } from 'react-router-dom'
import { ErrorState } from '@/components/states'

export default function NotFoundPage() {
  return <ErrorState status={404} title="Page not found"
                     detail={<><Link to="/"><Button type="primary">Go to the start page</Button></Link></>} />
}
