import * as ImagePicker from "expo-image-picker";
import React, { useState } from "react";
import {
  ActivityIndicator,
  Image,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ScanResponse, scanBookshelf } from "../api/client";
import AppButton from "../components/AppButton";
import ErrorBanner from "../components/ErrorBanner";
import { theme } from "../theme";

type Props = {
  onScanComplete: (result: ScanResponse) => void;
};

export default function CaptureScreen({ onScanComplete }: Props) {
  const [uri, setUri] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function pickImage(source: "camera" | "library") {
    setError("");
    setNotice("");
    const permission =
      source === "camera"
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();

    if (!permission.granted) {
      setError("Camera or photo library permission is required.");
      return;
    }

    const result =
      source === "camera"
        ? await ImagePicker.launchCameraAsync({ quality: 0.75, allowsEditing: false })
        : await ImagePicker.launchImageLibraryAsync({ quality: 0.75, allowsEditing: false });

    if (!result.canceled && result.assets[0]?.uri) {
      setUri(result.assets[0].uri);
    }
  }

  async function handleScan(useStub: boolean) {
    if (!uri) {
      setError("Take or choose a bookshelf photo first.");
      return;
    }

    setLoading(true);
    setError("");
    setNotice("");
    try {
      const response = await scanBookshelf(uri, useStub);
      const warnings = response.metrics.warnings ?? [];

      if (warnings.includes("zero_detections_fallback_full_image")) {
        setNotice("No spines detected — we scanned the full photo instead.");
      } else if (warnings.includes("daily_vlm_cap_reached")) {
        setError("Daily vision API limit reached. Try again tomorrow.");
        return;
      } else if (warnings.some((w) => w.startsWith("vlm_"))) {
        setNotice("Some spines could not be read. Check the review screen.");
      }

      onScanComplete(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Network error while scanning.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
        <View style={styles.hero}>
          <Text style={styles.kicker}>Shelfie</Text>
          <Text style={styles.title}>Scan your shelf</Text>
          <Text style={styles.subtitle}>
            Point your camera at book spines. We crop locally, read titles with Gemini vision,
            then match against the catalog.
          </Text>
        </View>

        <ErrorBanner message={error} variant="error" />
        <ErrorBanner message={notice} variant={notice ? "warning" : "error"} />

        <View style={styles.previewFrame}>
          {uri ? (
            <Image source={{ uri }} style={styles.preview} resizeMode="cover" />
          ) : (
            <View style={styles.placeholder}>
              <Text style={styles.placeholderEmoji}>📚</Text>
              <Text style={styles.placeholderText}>Your bookshelf photo appears here</Text>
            </View>
          )}
        </View>

        <View style={styles.row}>
          <AppButton label="Take photo" onPress={() => pickImage("camera")} style={styles.half} />
          <AppButton
            label="Choose photo"
            variant="secondary"
            onPress={() => pickImage("library")}
            style={styles.half}
          />
        </View>

        {loading ? (
          <View style={styles.loadingBlock}>
            <ActivityIndicator size="large" color={theme.colors.primary} />
            <Text style={styles.loadingText}>Reading spines and matching titles…</Text>
          </View>
        ) : (
          <View style={styles.actions}>
            <AppButton label="Scan bookshelf" onPress={() => handleScan(false)} disabled={!uri} />
            <AppButton
              label="Demo without API"
              variant="ghost"
              onPress={() => handleScan(true)}
              disabled={!uri}
            />
          </View>
        )}

        <View style={styles.tipCard}>
          <Text style={styles.tipTitle}>Tips for best results</Text>
          <Text style={styles.tipItem}>• Fill the frame with spines facing the camera</Text>
          <Text style={styles.tipItem}>• Avoid glare and motion blur</Text>
          <Text style={styles.tipItem}>• Scans are capped to protect your API key</Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.colors.bg },
  container: { padding: theme.spacing.lg, paddingBottom: theme.spacing.xl },
  hero: { marginBottom: theme.spacing.lg },
  kicker: {
    color: theme.colors.accent,
    fontSize: 13,
    fontWeight: "800",
    letterSpacing: 1.2,
    textTransform: "uppercase",
    marginBottom: 6,
  },
  title: {
    fontSize: 34,
    fontWeight: "800",
    color: theme.colors.text,
    lineHeight: 40,
  },
  subtitle: {
    marginTop: theme.spacing.sm,
    fontSize: 15,
    lineHeight: 22,
    color: theme.colors.textMuted,
  },
  previewFrame: {
    borderRadius: theme.radius.lg,
    overflow: "hidden",
    backgroundColor: theme.colors.surface,
    borderWidth: 1,
    borderColor: theme.colors.border,
    marginBottom: theme.spacing.md,
    ...theme.shadow.card,
  },
  preview: { width: "100%", height: 280 },
  placeholder: {
    height: 280,
    alignItems: "center",
    justifyContent: "center",
    padding: theme.spacing.lg,
  },
  placeholderEmoji: { fontSize: 42, marginBottom: theme.spacing.sm },
  placeholderText: { textAlign: "center", color: theme.colors.textMuted, fontSize: 15 },
  row: { flexDirection: "row", gap: theme.spacing.sm, marginBottom: theme.spacing.md },
  half: { flex: 1 },
  actions: { gap: theme.spacing.sm, marginBottom: theme.spacing.lg },
  loadingBlock: { alignItems: "center", gap: theme.spacing.sm, paddingVertical: theme.spacing.lg },
  loadingText: { color: theme.colors.textMuted, fontSize: 14 },
  tipCard: {
    backgroundColor: theme.colors.surface,
    borderRadius: theme.radius.md,
    padding: theme.spacing.md,
    borderWidth: 1,
    borderColor: theme.colors.border,
  },
  tipTitle: { fontWeight: "700", color: theme.colors.text, marginBottom: 8, fontSize: 15 },
  tipItem: { color: theme.colors.textMuted, lineHeight: 22, fontSize: 14 },
});
