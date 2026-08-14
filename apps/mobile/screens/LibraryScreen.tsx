import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";
import { useFocusEffect } from "@react-navigation/native";

import { LibraryEntry, getLibrary } from "../api/client";
import BookCard from "../components/BookCard";
import ErrorBanner from "../components/ErrorBanner";
import ScreenHeader from "../components/ScreenHeader";
import { theme } from "../theme";

function formatSavedDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return "";
  }
}

export default function LibraryScreen() {
  const insets = useSafeAreaInsets();
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setEntries(await getLibrary());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load library.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );

  const countLabel = `${entries.length} saved ${entries.length === 1 ? "book" : "books"}`;

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScreenHeader kicker="Your collection" title="Library" subtitle={countLabel} />

      <View style={styles.body}>
        <ErrorBanner message={error} />

        {loading ? (
          <ActivityIndicator size="large" color={theme.colors.primary} style={styles.loader} />
        ) : (
          <FlatList
            data={entries}
            keyExtractor={(item) => String(item.id)}
            contentContainerStyle={[
              styles.list,
              { paddingBottom: Math.max(insets.bottom, 16) + 88 },
            ]}
            ItemSeparatorComponent={() => <View style={styles.separator} />}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                tintColor={theme.colors.primary}
                onRefresh={() => {
                  setRefreshing(true);
                  load();
                }}
              />
            }
            renderItem={({ item }) => {
              const matched = Boolean(item.catalog_book_id);
              const readDiffers =
                matched &&
                (item.raw_title.trim().toLowerCase() !== item.title.trim().toLowerCase() ||
                  item.raw_author.trim().toLowerCase() !== item.author.trim().toLowerCase());

              return (
                <BookCard
                  title={item.title || item.raw_title || "Untitled"}
                  author={item.author || item.raw_author || "Author unknown"}
                  confidence={item.confidence_score}
                  showConfidence={item.confidence_score > 0}
                  badge={matched ? "Catalog match" : undefined}
                  subtitle={
                    readDiffers
                      ? `Read as “${item.raw_title}” · ${formatSavedDate(item.created_at)}`
                      : `Added ${formatSavedDate(item.created_at)}`
                  }
                />
              );
            }}
            ListEmptyComponent={
              <View style={styles.empty}>
                <Text style={styles.emptyEmoji}>📖</Text>
                <Text style={styles.emptyTitle}>No books yet</Text>
                <Text style={styles.emptyBody}>
                  Scan a shelf, confirm your matches on the review screen, then save them here.
                </Text>
              </View>
            }
          />
        )}
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  body: { flex: 1, paddingHorizontal: theme.spacing.lg },
  loader: { marginTop: 40 },
  list: { paddingTop: theme.spacing.xs },
  separator: { height: theme.spacing.sm },
  empty: { alignItems: "center", paddingTop: 48, paddingHorizontal: theme.spacing.md },
  emptyEmoji: { fontSize: 42, marginBottom: theme.spacing.sm },
  emptyTitle: { fontSize: 20, fontWeight: "700", color: theme.colors.text },
  emptyBody: {
    textAlign: "center",
    color: theme.colors.textMuted,
    marginTop: 8,
    lineHeight: 22,
    fontSize: 15,
  },
});
