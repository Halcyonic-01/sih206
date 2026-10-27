import { t as tr, useLanguage } from '@/i18n';
import { Input } from 'antd'
import { useNavigate } from 'react-router-dom'

export default function HeaderSearch() {
  useLanguage();
  const navigate = useNavigate()
  return <Input.Search type="search" aria-label={tr("Global record search")} placeholder={tr("Search deposits by reference, bank or institution")} allowClear
    onSearch={(value) => navigate(`/records?q=${encodeURIComponent(value)}`)} />
}
