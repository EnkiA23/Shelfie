import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  ViewStyle,
} from "react-native";

import { theme } from "../theme";

type Variant = "primary" | "secondary" | "ghost" | "danger";

type Props = {
  label: string;
  onPress: () => void;
  variant?: Variant;
  disabled?: boolean;
  loading?: boolean;
  style?: ViewStyle;
};

export default function AppButton({
  label,
  onPress,
  variant = "primary",
  disabled = false,
  loading = false,
  style,
}: Props) {
  const palette = {
    primary: { bg: theme.colors.primary, text: theme.colors.white, border: theme.colors.primary },
    secondary: { bg: theme.colors.accentSoft, text: theme.colors.accent, border: theme.colors.accentSoft },
    ghost: { bg: "transparent", text: theme.colors.primary, border: theme.colors.border },
    danger: { bg: theme.colors.errorBg, text: theme.colors.error, border: theme.colors.errorBg },
  }[variant];

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.base,
        {
          backgroundColor: palette.bg,
          borderColor: palette.border,
          opacity: disabled ? 0.5 : pressed ? 0.88 : 1,
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={palette.text} />
      ) : (
        <Text style={[styles.label, { color: palette.text }]}>{label}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    minHeight: 52,
    borderRadius: theme.radius.pill,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: theme.spacing.lg,
  },
  label: {
    fontSize: 16,
    fontWeight: "700",
    letterSpacing: 0.2,
  },
});
