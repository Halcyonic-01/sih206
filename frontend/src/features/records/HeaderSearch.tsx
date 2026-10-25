import { Input } from 'antd'
import { useNavigate } from 'react-router-dom'

export default function HeaderSearch() {
  const navigate = useNavigate()
  return <Input.Search aria-label="Global record search" placeholder="Search deposits by reference, bank or institution" allowClear
    onSearch={(value) => navigate(`/records?q=${encodeURIComponent(value)}`)} />
}
