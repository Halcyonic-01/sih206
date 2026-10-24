import type { ThemeConfig } from 'antd'

export const theme: ThemeConfig = {
  token: {
    colorPrimary: '#1d3f72',
    colorInfo: '#1d3f72',
    borderRadius: 4,
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Noto Sans', 'Noto Sans Devanagari', sans-serif",
  },
  components: {
    Layout: { siderBg: '#14294a', headerBg: '#ffffff', bodyBg: '#f4f6fa' },
    Menu: { darkItemBg: '#14294a' },
  },
}
