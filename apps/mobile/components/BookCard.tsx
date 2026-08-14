import React from "react";
import { Image, Pressable, StyleSheet, Text, View } from "react-native";

import { theme } from "../theme";

type Props = {
  title: string;
  author?: string;
  confidence?: number;
  subtitle?: string;
  thumbnail?: string | null;
  badge?: string;
  onPress?: () => void;
  rightSlot?: React.ReactNode;
  showConfidence?: boolean;
};

export default function BookCard({
  title,
  author,
  confidence,
  subtitle,
  thumbnail,
  badge,
  onPress,
  rightSlot,
  showConfidence = true,
}: Props) {
  const content = (
    <>
      <View style={styles.headerRow}>
        {thumbnail ? (
          <Image source={{ uri: thumbnail }} style={styles.thumbnail} resizeMode="cover" />
        ) : (
          <View style={styles.placeholderThumb}>
            <Text style={styles.placeholderEmoji}>📖</Text>
          </View>
        )}
        <View style={styles.textBlock}>
          {badge ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{badge}</Text>
            </View>
          ) : null}
          <Text style={styles.title} numberOfLines={3}>
            {title}
          </Text>
          {author ? (
            <Text style={styles.author} numberOfLines={2}>
              {author}
            </Text>
          ) : null}
          {subtitle ? (
            <Text style={styles.subtitle} numberOfLines={2}>
              {subtitle}
            </Text>
          ) : null}
        </View>
        {rightSlot}
      </View>
      {showConfidence && typeof confidence === "number" ? (
        <View style={styles.confidenceWrap}>
          <View style={styles.confidenceTrack}>
            <View style={[styles.confidenceBar, { width: `${Math.min(confidence * 100, 100)}%` }]} />
          </View>
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
    borderWidth: 1,
    borderColor: theme.colors.border,
    ...theme.shadow.card,
  },
  pressed: { opacity: 0.92 },
  headerRow: { flexDirection: "row", alignItems: "flex-start" },
  thumbnail: {
    width: 48,
    height: 72,
    borderRadius: theme.radius.sm,
    marginRight: theme.spacing.sm,
    backgroundColor: theme.colors.border,
  },
  placeholderThumb: {
    width: 48,
    height: 72,
    borderRadius: theme.radius.sm,
    marginRight: theme.spacing.sm,
    backgroundColor: theme.colors.accentSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  placeholderEmoji: { fontSize: 22 },
  textBlock: { flex: 1, minWidth: 0 },
  badge: {
    alignSelf: "flex-start",
    backgroundColor: theme.colors.successBg,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: theme.radius.pill,
    marginBottom: 6,
  },
  badgeText: {
    fontSize: 11,
    fontWeight: "700",
    color: theme.colors.success,
    textTransform: "uppercase",
    letterSpacing: 0.4,
  },
  title: {
    fontSize: 17,
    fontWeight: "700",
    color: theme.colors.text,
    lineHeight: 23,
  },
  author: {
    marginTop: 4,
    fontSize: 14,
    color: theme.colors.textMuted,
    lineHeight: 20,
  },
  subtitle: {
    marginTop: 6,
    fontSize: 12,
    color: theme.colors.textMuted,
    lineHeight: 17,
  },
  confidenceWrap: { marginTop: theme.spacing.sm },
  confidenceTrack: {
    height: 6,
    backgroundColor: theme.colors.border,
    borderRadius: theme.radius.pill,
    overflow: "hidden",
  },
  confidenceBar: {
    height: "100%",
    backgroundColor: theme.colors.success,
    borderRadius: theme.radius.pill,
  },
  confidenceText: {
    marginTop: 6,
    fontSize: 12,
    fontWeight: "600",
    color: theme.colors.success,
  },
});
