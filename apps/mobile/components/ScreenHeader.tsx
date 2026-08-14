import React from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";

import { theme } from "../theme";

type Props = {
  kicker?: string;
  title: string;
  subtitle?: string;
  style?: ViewStyle;
};

export default function ScreenHeader({ kicker, title, subtitle, style }: Props) {
  return (
    <View style={[styles.wrap, style]}>
      {kicker ? <Text style={styles.kicker}>{kicker}</Text> : null}
      <Text style={styles.title}>{title}</Text>
      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    paddingHorizontal: theme.spacing.lg,
    paddingTop: theme.spacing.md,
    paddingBottom: theme.spacing.sm,
  },
  kicker: {
    color: theme.colors.accent,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
    marginBottom: 4,
  },
  title: {
    fontSize: 28,
    fontWeight: "800",
    color: theme.colors.text,
    lineHeight: 34,
  },
  subtitle: {
    marginTop: 6,
    color: theme.colors.textMuted,
    fontSize: 14,
    lineHeight: 20,
  },
});
