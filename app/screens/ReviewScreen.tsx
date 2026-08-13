import React, { useEffect, useState } from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import {
  CatalogBook,
  ScanItem,
  ScanResponse,
  saveLibraryEntry,
  searchCatalog,
} from "../api/client";
import AppButton from "../components/AppButton";
import BookCard from "../components/BookCard";
import ErrorBanner from "../components/ErrorBanner";
import { theme } from "../theme";

type Props = {
  scanResult: ScanResponse | null;
  onSaved: () => void;
  onBack: () => void;
};

type EditableItem = ScanItem & {
  editTitle: string;
  editAuthor: string;
  selectedCatalogId?: number | null;
};

function toEditable(item: ScanItem): EditableItem {
  return {
    ...item,
    editTitle: item.extracted_title || item.matched_book?.title || "",
    editAuthor: item.extracted_author || item.matched_book?.author || "",
    selectedCatalogId: item.matched_book?.catalog_book_id ?? null,
  };
}

export default function ReviewScreen({ scanResult, onSaved, onBack }: Props) {
  const [high, setHigh] = useState<EditableItem[]>([]);
  const [review, setReview] = useState<EditableItem[]>([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [activeSearch, setActiveSearch] = useState<number | null>(null);
  const [searchResults, setSearchResults] = useState<CatalogBook[]>([]);

  useEffect(() => {
    if (!scanResult) {
      setHigh([]);
      setReview([]);
      return;
    }
    setHigh(scanResult.high_confidence.map(toEditable));
    setReview(scanResult.needs_review.map(toEditable));
  }, [scanResult]);

  async function persistItems(items: EditableItem[]) {
    if (!items.length) return;
    setSaving(true);
    setError("");
    try {
      for (const item of items) {
        await saveLibraryEntry({
          catalog_book_id: item.selectedCatalogId,
          raw_title: item.editTitle.trim(),
          raw_author: item.editAuthor.trim(),
          confidence_score: item.confidence_score,
        });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save to library.");
    } finally {
      setSaving(false);
    }
  }

  async function handleSearch(index: number, query: string, section: "high" | "review") {
    const setter = section === "high" ? setHigh : setReview;
    const list = section === "high" ? high : review;
    const updated = [...list];
    updated[index] = { ...updated[index], editTitle: query };
    setter(updated);
    setActiveSearch(index);

    if (query.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    try {
      setSearchResults(await searchCatalog(query.trim()));
    } catch {
      setSearchResults([]);
    }
  }

  function renderEditableCard(
    item: EditableItem,
    index: number,
    section: "high" | "review",
    onDiscard: () => void,
  ) {
    return (
      <View key={`${section}-${index}`} style={styles.editCard}>
        <BookCard
          title={item.editTitle || "Unknown title"}
          author={item.editAuthor || "Unknown author"}
          confidence={item.confidence_score}
          thumbnail={item.crop_thumbnail}
          subtitle={
            item.warnings?.length
              ? "This spine could not be read — edit or discard it."
              : item.alternatives?.length
                ? `Also consider: ${item.alternatives.map((a) => a.title).join(", ")}`
                : undefined
          }
        />
        <TextInput
          style={styles.input}
          value={item.editTitle}
          onChangeText={(text) => handleSearch(index, text, section)}
          placeholder="Edit title"
          placeholderTextColor={theme.colors.textMuted}
        />
        <TextInput
          style={styles.input}
          value={item.editAuthor}
          onChangeText={(text) => {
            const setter = section === "high" ? setHigh : setReview;
            const list = section === "high" ? high : review;
            const updated = [...list];
            updated[index] = { ...updated[index], editAuthor: text };
            setter(updated);
          }}
          placeholder="Edit author"
          placeholderTextColor={theme.colors.textMuted}
        />
        {activeSearch === index && searchResults.length > 0 ? (
          <View style={styles.suggestions}>
            {searchResults.map((book) => (
              <Text
                key={book.id}
                style={styles.suggestion}
                onPress={() => {
                  const setter = section === "high" ? setHigh : setReview;
                  const list = section === "high" ? high : review;
                  const updated = [...list];
                  updated[index] = {
                    ...updated[index],
                    editTitle: book.title,
                    editAuthor: book.author,
                    selectedCatalogId: book.id,
                  };
                  setter(updated);
                  setSearchResults([]);
                  setActiveSearch(null);
                }}
              >
                {book.title} — {book.author}
              </Text>
            ))}
          </View>
        ) : null}
        <AppButton label="Discard" variant="danger" onPress={onDiscard} />
      </View>
    );
  }

  if (!scanResult) {
    return (
      <SafeAreaView style={styles.safe}>
        <View style={styles.emptyWrap}>
          <Text style={styles.emptyTitle}>Nothing to review yet</Text>
          <Text style={styles.emptyBody}>Scan a bookshelf from the Scan tab first.</Text>
          <AppButton label="Go back" variant="ghost" onPress={onBack} />
        </View>
      </SafeAreaView>
    );
  }

  const metrics = scanResult.metrics;

  return (
    <SafeAreaView style={styles.safe} edges={["bottom"]}>
      <ScrollView contentContainerStyle={styles.container}>
        <ErrorBanner message={error} />

        <View style={styles.metricsCard}>
          <Text style={styles.metricsTitle}>Scan summary</Text>
          <Text style={styles.metricsLine}>
            {metrics.spines_detected} spines · {metrics.spines_matched} auto-matched ·{" "}
            {metrics.latency_ms}ms
          </Text>
          <Text style={styles.metricsLine}>
            {metrics.detector_backend ?? "detector"} → {metrics.vlm_provider ?? "vlm"} · est. $
            {metrics.est_cost_usd.toFixed(5)}
          </Text>
        </View>

        <View style={styles.sectionHeader}>
          <Text style={styles.sectionTitle}>High confidence</Text>
          <Text style={styles.sectionCount}>{high.length}</Text>
        </View>
        <AppButton
          label={saving ? "Saving…" : `Add all (${high.length})`}
          onPress={() => persistItems(high)}
          disabled={saving || high.length === 0}
          loading={saving}
        />
        {high.map((item, index) =>
          renderEditableCard(item, index, "high", () => {
            setHigh((prev) => prev.filter((_, i) => i !== index));
          }),
        )}
        {high.length === 0 ? <Text style={styles.emptySection}>No auto-accepted matches.</Text> : null}

        <View style={[styles.sectionHeader, { marginTop: theme.spacing.lg }]}>
          <Text style={styles.sectionTitle}>Needs review</Text>
          <Text style={styles.sectionCount}>{review.length}</Text>
        </View>
        {review.map((item, index) =>
          renderEditableCard(item, index, "review", () => {
            setReview((prev) => prev.filter((_, i) => i !== index));
          }),
        )}
        {review.length === 0 ? (
          <Text style={styles.emptySection}>Everything looked good — nothing flagged.</Text>
        ) : null}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  container: { padding: theme.spacing.lg, paddingBottom: theme.spacing.xl },
  metricsCard: {
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    marginBottom: theme.spacing.lg,
  },
  metricsTitle: { color: theme.colors.white, fontWeight: "700", fontSize: 14, marginBottom: 4 },
  metricsLine: { color: "#DDE8DF", fontSize: 13, lineHeight: 20 },
  sectionHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: theme.spacing.sm,
  },
  sectionTitle: { fontSize: 20, fontWeight: "800", color: theme.colors.text },
  sectionCount: {
    backgroundColor: theme.colors.accentSoft,
    color: theme.colors.accent,
    fontWeight: "800",
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: theme.radius.pill,
    overflow: "hidden",
  },
  editCard: { marginTop: theme.spacing.md },
  input: {
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
    borderColor: theme.colors.border,
    borderRadius: theme.radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    marginBottom: theme.spacing.sm,
    color: theme.colors.text,
    fontSize: 15,
  },
  suggestions: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.radius.sm,
    borderWidth: 1,
    borderColor: theme.colors.border,
    marginBottom: theme.spacing.sm,
    overflow: "hidden",
  },
  suggestion: {
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: theme.colors.primary,
    borderBottomWidth: 1,
    borderBottomColor: theme.colors.border,
    fontWeight: "600",
  },
  emptySection: { color: theme.colors.textMuted, marginBottom: theme.spacing.md },
  emptyWrap: {
    flex: 1,
    justifyContent: "center",
    padding: theme.spacing.lg,
    gap: theme.spacing.sm,
  },
  emptyTitle: { fontSize: 24, fontWeight: "800", color: theme.colors.text },
  emptyBody: { color: theme.colors.textMuted, marginBottom: theme.spacing.md, lineHeight: 22 },
});
