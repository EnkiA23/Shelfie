import React from "react";
import { StyleSheet, Text, View } from "react-native";

import { theme } from "../theme";

type Props = {
  message: string;
  variant?: "error" | "warning" | "info" | "success";
};

export default function ErrorBanner({ message, variant = "error" }: Props) {
  if (!message) return null;

  const palette = {
    error: { bg: theme.colors.errorBg, text: theme.colors.error },
    warning: { bg: theme.colors.warningBg, text: theme.colors.warning },
    info: { bg: "#E8EEF8", text: "#355C9A" },
    success: { bg: theme.colors.successBg, text: theme.colors.success },
  }[variant];

  return (
    <View style={[styles.banner, { backgroundColor: palette.bg }]}>
      <Text style={[styles.text, { color: palette.text }]}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  banner: {
    padding: theme.spacing.md,
    borderRadius: theme.radius.md,
    marginBottom: theme.spacing.md,
  },
  text: {
    fontSize: 14,
    lineHeight: 20,
    fontWeight: "500",
  },
});
