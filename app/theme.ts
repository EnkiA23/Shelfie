export const theme = {
  colors: {
    bg: "#F4EFE6",
    surface: "#FFFCF7",
    primary: "#2F5233",
    primaryDark: "#1E3421",
    accent: "#B85C38",
    accentSoft: "#F3DDD2",
    text: "#1F1A17",
    textMuted: "#6B625B",
    border: "#E4D9CC",
    success: "#2F6B4F",
    successBg: "#E6F2EB",
    warning: "#9A6B1F",
    warningBg: "#FBF0D9",
    error: "#9B2C2C",
    errorBg: "#FCEAEA",
    white: "#FFFFFF",
  },
  radius: {
    sm: 10,
    md: 16,
    lg: 24,
    pill: 999,
  },
  spacing: {
    xs: 6,
    sm: 10,
    md: 16,
    lg: 24,
    xl: 32,
  },
  shadow: {
    card: {
      shadowColor: "#1F1A17",
      shadowOffset: { width: 0, height: 4 },
      shadowOpacity: 0.08,
      shadowRadius: 12,
      elevation: 3,
    },
  },
} as const;

export type Theme = typeof theme;
