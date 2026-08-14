import { Platform } from "react-native";

function defaultApiUrl(): string {
  if (Platform.OS === "android") {
    // Android emulator maps host machine localhost to 10.0.2.2
    return "http://10.0.2.2:8000";
  }
  return "http://127.0.0.1:8000";
}

const API_URL = process.env.EXPO_PUBLIC_API_URL ?? defaultApiUrl();
const API_TOKEN = process.env.EXPO_PUBLIC_API_TOKEN ?? "dev-token";

function formatApiError(text: string): string {
  try {
    const parsed = JSON.parse(text) as { detail?: string };
    if (parsed.detail) {
      return parsed.detail;
    }
  } catch {
    // keep raw text
  }
  return text || "Request failed.";
}

async function buildPhotoFormData(uri: string): Promise<FormData> {
  const form = new FormData();

  if (Platform.OS === "web") {
    const response = await fetch(uri);
    const blob = await response.blob();
    form.append(
      "photo",
      new File([blob], "bookshelf.jpg", { type: blob.type || "image/jpeg" }),
    );
  } else {
    form.append(
      "photo",
      {
        uri,
        name: "bookshelf.jpg",
        type: "image/jpeg",
      } as unknown as Blob,
    );
  }

  return form;
}

export type ScanItem = {
  crop_index: number;
  extracted_title: string;
  extracted_author: string;
  confidence_score: number;
  matched_book?: {
    catalog_book_id?: number;
    title: string;
    author: string;
    edition_info?: string;
    confidence_score: number;
  } | null;
  alternatives: Array<{
    catalog_book_id?: number;
    title: string;
    author: string;
    edition_info?: string;
    confidence_score: number;
  }>;
  crop_thumbnail?: string | null;
  warnings: string[];
};

export type ScanResponse = {
  high_confidence: ScanItem[];
  needs_review: ScanItem[];
  metrics: {
    latency_ms: number;
    stage1_ms?: number;
    stage2_ms?: number;
    est_cost_usd: number;
    spines_detected: number;
    spines_matched: number;
    detector_backend?: string;
    vlm_provider?: string;
    warnings?: string[];
  };
};

export type LibraryEntry = {
  id: number;
  catalog_book_id?: number | null;
  title: string;
  author: string;
  raw_title: string;
  raw_author: string;
  confidence_score: number;
  source_image?: string;
  created_at: string;
};

export type CatalogBook = {
  id: number;
  external_id: number;
  title: string;
  author: string;
  alternate_titles: string[];
  edition_info: string;
};

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    Authorization: `Bearer ${API_TOKEN}`,
    ...(options.headers as Record<string, string> | undefined),
  };

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(formatApiError(text) || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export async function scanBookshelf(uri: string, useStub = false): Promise<ScanResponse> {
  const form = await buildPhotoFormData(uri);
  const path = useStub ? "/api/scan/?stub=1" : "/api/scan/";
  return request<ScanResponse>(path, {
    method: "POST",
    body: form,
  });
}

export async function getLibrary(): Promise<LibraryEntry[]> {
  return request<LibraryEntry[]>("/api/library/");
}

export async function saveLibraryEntry(entry: {
  catalog_book_id?: number | null;
  raw_title: string;
  raw_author: string;
  confidence_score: number;
}): Promise<LibraryEntry> {
  return request<LibraryEntry>("/api/library/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(entry),
  });
}

export async function searchCatalog(query: string): Promise<CatalogBook[]> {
  const encoded = encodeURIComponent(query);
  return request<CatalogBook[]>(`/api/catalog/search/?q=${encoded}`);
}
