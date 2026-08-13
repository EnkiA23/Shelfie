import React, { useCallback, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useFocusEffect } from "@react-navigation/native";

import { LibraryEntry, getLibrary } from "../api/client";
import BookCard from "../components/BookCard";
import ErrorBanner from "../components/ErrorBanner";
import { theme } from "../theme";

export default function LibraryScreen() {
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

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <View style={styles.header}>
        <Text style={styles.kicker}>Your collection</Text>
        <Text style={styles.title}>Library</Text>
        <Text style={styles.subtitle}>{entries.length} saved {entries.length === 1 ? "book" : "books"}</Text>
      </View>

      <ErrorBanner message={error} />

      {loading ? (
        <ActivityIndicator size="large" color={theme.colors.primary} style={{ marginTop: 40 }} />
      ) : (
        <FlatList
          data={entries}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={styles.list}
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
          renderItem={({ item }) => (
            <BookCard
              title={item.raw_title}
              author={item.raw_author || "Unknown author"}
              confidence={item.confidence_score}
              subtitle={new Date(item.created_at).toLocaleDateString()}
            />
          )}
          ListEmptyComponent={
            <View style={styles.empty}>
              <Text style={styles.emptyEmoji}>📖</Text>
              <Text style={styles.emptyTitle}>No books yet</Text>
              <Text style={styles.emptyBody}>
                Scan a shelf and confirm matches to build your library.
              </Text>
            </View>
          }
        />
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  header: { paddingHorizontal: theme.spacing.lg, paddingTop: theme.spacing.md, paddingBottom: theme.spacing.sm },
  kicker: {
    color: theme.colors.accent,
    fontSize: 12,
    fontWeight: "800",
    letterSpacing: 1,
    textTransform: "uppercase",
  },
  title: { fontSize: 32, fontWeight: "800", color: theme.colors.text, marginTop: 4 },
  subtitle: { marginTop: 4, color: theme.colors.textMuted, fontSize: 14 },
  list: { paddingHorizontal: theme.spacing.lg, paddingBottom: theme.spacing.xl },
  empty: { alignItems: "center", paddingTop: 60, paddingHorizontal: theme.spacing.lg },
  emptyEmoji: { fontSize: 42, marginBottom: theme.spacing.sm },
  emptyTitle: { fontSize: 20, fontWeight: "700", color: theme.colors.text },
  emptyBody: { textAlign: "center", color: theme.colors.textMuted, marginTop: 8, lineHeight: 22 },
});
