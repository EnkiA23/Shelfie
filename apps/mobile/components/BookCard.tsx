import React from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";

import { theme } from "../theme";

type Props = {
  title: string;
  author?: string;
  confidence?: number;
  subtitle?: string;
  thumbnail?: string | null;
  onPress?: () => void;
  rightSlot?: React.ReactNode;
};

export default function BookCard({
  title,
  author,
  confidence,
  subtitle,
  thumbnail,
  onPress,
  rightSlot,
}: Props) {
  const content = (
    <>
      <View style={styles.headerRow}>
        {thumbnail ? (
          <Image source={{ uri: thumbnail }} style={styles.thumbnail} resizeMode="cover" />
        ) : null}
        <View style={styles.textBlock}>
          <Text style={styles.title} numberOfLines={2}>
            {title}
          </Text>
          {author ? <Text style={styles.author}>{author}</Text> : null}
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
        </View>
        {rightSlot}
      </View>
      {typeof confidence === "number" ? (
        <View style={styles.confidenceRow}>
          <View style={[styles.confidenceBar, { width: `${Math.min(confidence * 100, 100)}%` }]} />
          <Text style={styles.confidenceText}>{Math.round(confidence * 100)}% match</Text>
        </View>
      ) : null}
    </>
  );

  if (onPress) {
    return (
      <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
        {content}
      </Pressable>
    );
  }

  return <View style={styles.card}>{content}</View>;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
    ...theme.shadow.card,
  },
  pressed: { opacity: 0.92 },
  headerRow: { flexDirection: "row", alignItems: "flex-start" },
  thumbnail: {
    width: 44,
    height: 66,
    borderRadius: theme.radius.sm,
    marginRight: theme.spacing.sm,
    backgroundColor: theme.colors.border,
  },
  textBlock: { flex: 1, paddingRight: theme.spacing.sm },
  title: {
    fontSize: 17,
    fontWeight: "700",
    color: theme.colors.text,
    lineHeight: 24,
  },
  author: {
    marginTop: 4,
    fontSize: 14,
    color: theme.colors.textMuted,
  },
  subtitle: {
    marginTop: 6,
    fontSize: 12,
    color: theme.colors.textMuted,
  },
  confidenceRow: {
    marginTop: theme.spacing.sm,
    height: 8,
    backgroundColor: theme.colors.border,
    borderRadius: theme.radius.pill,
    overflow: "hidden",
  },
  confidenceBar: {
    position: "absolute",
    left: 0,
    top: 0,
    bottom: 0,
    backgroundColor: theme.colors.success,
    borderRadius: theme.radius.pill,
  },
  confidenceText: {
    marginTop: 8,
    fontSize: 12,
    fontWeight: "600",
    color: theme.colors.success,
  },
});
