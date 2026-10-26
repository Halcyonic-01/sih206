import type { ThemeConfig } from 'antd'

/**
 * Design tokens for the whole portal. The same values exist as CSS variables in styles.css; change both together.
 * Warm cream, navy and orange reference the observed official internship portal.
 * Orange is decorative; darkened orange is used for text so contrast is retained.
 */
export const colors = {
  primary: '#172554',
  primaryHover: '#30467f',
  navy: '#172554',
  navyActive: '#30467f',
  accent: '#e85d04',
  accentText: '#a94400',
  success: '#14703a',
  warning: '#8a4b08',
  error: '#b42318',
  text: '#1b1140',
  textSecondary: '#525767',
  textMuted: '#626474',
  border: '#e7e2d8',
  borderStrong: '#8a8791',
  surface: '#ffffff',
  page: '#fffcf6',
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
      itemBorderRadius: 6,
      itemMarginInline: 12,
      itemHeight: 44,
      itemSelectedBg: '#fff1e5',
      itemSelectedColor: '#8f3b00',
      itemHoverBg: '#faf6ee',
      itemColor: colors.textSecondary,
      iconSize: 17,
    },
    Card: { headerFontSize: 16, headerHeight: 52, bodyPadding: 20, bodyPaddingSM: 14 },
    Table: {
      headerBg: '#f5f2eb',
      headerColor: colors.text,
      headerSplitColor: 'transparent',
      rowHoverBg: '#fff9ed',
      cellPaddingBlock: 12,
      cellPaddingInline: 14,
      borderColor: colors.border,
    },
    Button: { fontWeight: 600, primaryShadow: 'none', defaultShadow: 'none', contentFontSize: 15 },
    Tabs: { titleFontSize: 15, horizontalMargin: '0 0 16px' },
    Form: { labelColor: colors.text, verticalLabelPadding: '0 0 6px' },
    Tag: { defaultBg: '#eceff4', defaultColor: '#3a465a' },
    Alert: { withDescriptionPadding: '14px 16px' },
    Segmented: { trackBg: '#f0ece3' },
  },
}
