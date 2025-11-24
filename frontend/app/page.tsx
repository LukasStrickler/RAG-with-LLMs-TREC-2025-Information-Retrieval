"use client";

import { useState } from "react";
import { SearchBar } from "@/components/search-bar";
import { SearchFilters } from "@/components/search-filters";
import { SearchResults } from "@/components/search-results";
import { searchDocuments } from "@/lib/api";
import type { RetrievedSegment } from "@/lib/types";

export default function Home() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"lexical" | "vector" | "hybrid">("hybrid");
  const [topK, setTopK] = useState(20);
  const [results, setResults] = useState<RetrievedSegment[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchPerformed, setSearchPerformed] = useState(false);

  const handleSearch = async () => {
    if (!query.trim()) return;

    setIsLoading(true);
    setError(null);
    setSearchPerformed(true);

    try {
      const response = await searchDocuments(query, mode, topK);
      const segments = response.results[0]?.segments || [];
      setResults(segments);
    } catch (err) {
      console.error("Search error:", err);
      const errorMessage = err instanceof Error
        ? err.message
        : typeof err === "string"
          ? err
          : "An unexpected error occurred";
      setError(errorMessage);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="container mx-auto px-4 py-4">
          <h1 className="text-2xl font-bold text-blue-600">
            TREC 2025 Retrieval
          </h1>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8">
        <div
          className={`flex flex-col items-center gap-8 transition-all duration-300 ${searchPerformed ? "mt-4" : "mt-32"
            }`}
        >
          {/* Search Bar */}
          <SearchBar
            value={query}
            onChange={setQuery}
            onSearch={handleSearch}
            placeholder="Search documents..."
          />

          {/* Filters */}
          <SearchFilters
            mode={mode}
            onModeChange={setMode}
            topK={topK}
            onTopKChange={setTopK}
          />

          {/* Error Message */}
          {error && (
            <div className="w-full max-w-3xl p-4 bg-destructive/10 border border-destructive rounded-lg">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* Results */}
          <SearchResults
            segments={results}
            isLoading={isLoading}
            searchPerformed={searchPerformed}
          />
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t mt-16">
        <div className="container mx-auto px-4 py-6 text-center text-sm text-muted-foreground">
          TREC 2025 Information Retrieval Track
        </div>
      </footer>
    </div>
  );
}
