import type { ThemeConfig } from 'antd'

/**
 * Design tokens for the whole portal. The same values exist as CSS variables in styles.css; change both together.
 * Every text colour here meets WCAG 2.1 AA (4.5:1) on its background and every control border meets 3:1.
 */
export const colors = {
  primary: '#1a3f7a',
  primaryHover: '#2a55a0',
  navy: '#0f2447',
  navyActive: '#1f4a8c',
  accent: '#e8791d',
  accentText: '#a8480a',
  success: '#14703a',
  warning: '#8a4b08',
  error: '#b42318',
  text: '#1b2433',
  textSecondary: '#4b586b',
  textMuted: '#5f6b7d',
  border: '#dde3ec',
  borderStrong: '#7b889c',
  surface: '#ffffff',
  page: '#f3f5f9',
} as const

export const fontFamily =
  "system-ui, -apple-system, 'Segoe UI', Roboto, 'Noto Sans', 'Noto Sans Devanagari', 'Helvetica Neue', Arial, sans-serif"

export const theme: ThemeConfig = {
  token: {
    colorPrimary: colors.primary,
    colorInfo: colors.primary,
    colorSuccess: colors.success,
    colorWarning: '#b45309',
    colorError: colors.error,
    colorSuccessBg: '#e6f4ec',
    colorSuccessBorder: '#a9d7bb',
    colorWarningBg: '#fdf1e0',
    colorWarningBorder: '#f2c98f',
    colorErrorBg: '#fdecea',
    colorErrorBorder: '#f0b4ae',
    colorInfoBg: '#e8eef8',
    colorInfoBorder: '#b8c9e6',
    colorLink: '#1a56b0',
    colorText: colors.text,
    colorTextSecondary: colors.textSecondary,
    colorTextDescription: colors.textMuted,
    colorTextPlaceholder: '#6b778a',
    colorBgLayout: colors.page,
    colorBorder: colors.borderStrong,
    colorBorderSecondary: colors.border,
    borderRadius: 8,
    borderRadiusSM: 6,
    borderRadiusLG: 12,
    fontFamily,
    fontSize: 15,
    controlHeight: 40,
    lineHeight: 1.6,
    wireframe: false,
  },
  components: {
    Layout: { siderBg: colors.navy, headerBg: colors.surface, bodyBg: colors.page, headerHeight: 64, headerPadding: '0 24px' },
    Menu: {
      darkItemBg: colors.navy,
      darkSubMenuItemBg: colors.navy,
      darkItemColor: '#c9d4e6',
      darkItemHoverColor: '#ffffff',
      darkItemHoverBg: 'rgba(255,255,255,0.08)',
      darkItemSelectedBg: colors.navyActive,
      darkItemSelectedColor: '#ffffff',
      darkGroupTitleColor: '#8fa3c4',
      itemBorderRadius: 8,
      itemMarginInline: 12,
      itemHeight: 42,
      iconSize: 17,
    },
    Card: { headerFontSize: 16, headerHeight: 52, bodyPadding: 20, bodyPaddingSM: 14 },
    Table: {
      headerBg: '#eef2f8',
      headerColor: colors.text,
      headerSplitColor: 'transparent',
      rowHoverBg: '#f6f8fc',
      cellPaddingBlock: 12,
      cellPaddingInline: 14,
      borderColor: colors.border,
    },
    Button: { fontWeight: 600, primaryShadow: 'none', defaultShadow: 'none', contentFontSize: 15 },
    Tabs: { titleFontSize: 15, horizontalMargin: '0 0 16px' },
    Form: { labelColor: colors.text, verticalLabelPadding: '0 0 6px' },
    Tag: { defaultBg: '#eceff4', defaultColor: '#3a465a' },
    Alert: { withDescriptionPadding: '14px 16px' },
    Segmented: { trackBg: '#e6ebf3' },
  },
}
