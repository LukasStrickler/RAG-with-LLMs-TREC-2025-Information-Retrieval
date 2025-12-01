import axios from "axios";
import type { RetrievalRequest, RetrievalResponse } from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

// Trigger CI workflow

const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
    "X-API-Key": API_KEY,
  },
});

export async function searchDocuments(
  queryText: string,
  mode: "lexical" | "vector" | "hybrid" = "hybrid",
  topK: number = 10,
): Promise<RetrievalResponse> {
  const request: RetrievalRequest = {
    mode,
    queries: [
      {
        query_id: `query_${Date.now()}`,
        query_text: queryText,
        top_k: topK,
      },
    ],
  };

  console.log("API Request:", {
    url: `${API_URL}/api/v1/retrieve`,
    apiKey: API_KEY ? `***${API_KEY.slice(-4)}` : "NOT SET",
    request,
  });

  try {
    const response = await apiClient.post<RetrievalResponse>(
      "/api/v1/retrieve",
      request,
    );
    console.log("API Response:", response.data);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      // Extract error message from response
      const errorMessage =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Failed to fetch search results";
      throw new Error(errorMessage);
    }
    if (error instanceof Error) {
      throw new Error(error.message);
    }
    throw new Error("An unknown error occurred");
  }
}

export async function getDocument(docId: string): Promise<unknown> {
  try {
    const response = await apiClient.get<unknown>(`/api/v1/document/${docId}`);
    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const errorMessage =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "Failed to fetch document";
      throw new Error(errorMessage);
    }
    if (error instanceof Error) {
      throw new Error(error.message);
    }
    throw new Error("An unknown error occurred");
  }
}
