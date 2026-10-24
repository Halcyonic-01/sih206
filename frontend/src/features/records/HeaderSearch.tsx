import {Input} from 'antd'
import {useNavigate} from 'react-router-dom'

export default function HeaderSearch() {
  const navigate = useNavigate()
  return <Input.Search aria-label="Global record search" placeholder="Search deposit records" allowClear
    onSearch={value => navigate(`/records?q=${encodeURIComponent(value)}`)} style={{width: 280, maxWidth: '100%'}}/>
}
