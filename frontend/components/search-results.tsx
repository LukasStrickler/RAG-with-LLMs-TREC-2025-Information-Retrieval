"use client";

import { ExternalLink, FileText } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import type { RetrievedSegment } from "@/lib/types";

interface SearchResultsProps {
  segments: RetrievedSegment[];
  isLoading: boolean;
  searchPerformed: boolean;
}

export function SearchResults({
  segments,
  isLoading,
  searchPerformed,
}: SearchResultsProps) {
  if (isLoading) {
    return (
      <div className="w-full max-w-3xl space-y-4">
        {[...Array(3)].map((_, i) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: Skeleton loader items are static
          <Card key={i} className="animate-pulse">
            <CardHeader>
              <div className="h-6 bg-muted rounded w-3/4" />
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="h-4 bg-muted rounded" />
                <div className="h-4 bg-muted rounded w-5/6" />
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (!searchPerformed) {
    return null;
  }

  if (segments.length === 0) {
    return (
      <div className="w-full max-w-3xl">
        <Card className="border-dashed">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <FileText className="h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-lg font-medium text-muted-foreground">
              No results found
            </p>
            <p className="text-sm text-muted-foreground mt-2">
              Try adjusting your search query or filters
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="w-full max-w-3xl space-y-4">
      <div className="text-sm text-muted-foreground mb-4">
        About {segments.length} results
      </div>
      {segments.map((segment, index) => (
        <Card
          key={segment.segment_id}
          className="hover:shadow-md transition-shadow cursor-pointer group"
        >
          <CardHeader className="pb-3">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1 min-w-0">
                {segment.metadata.url && (
                  <a
                    href={segment.metadata.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-600 hover:underline flex items-center gap-1 mb-1 truncate"
                  >
                    {new URL(segment.metadata.url).hostname}
                    <ExternalLink className="h-3 w-3 flex-shrink-0" />
                  </a>
                )}
                <Link
                  href={`/document/${segment.segment_id}`}
                  className="block group-hover:underline"
                >
                  <h3 className="text-xl font-medium text-blue-700 line-clamp-2">
                    {segment.metadata.title || `Document ${index + 1}`}
                  </h3>
                </Link>
              </div>
              <Badge variant="secondary" className="flex-shrink-0">
                {segment.score.toFixed(4)}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-foreground/80 line-clamp-3">
              {segment.content}
            </p>
            <div className="flex gap-2 mt-3 flex-wrap">
              <Badge variant="outline" className="text-xs">
                {segment.provenance.index_kind}
              </Badge>
              {segment.metadata.extras?.source && (
                <Badge variant="secondary" className="text-xs">
                  Source: {segment.metadata.extras.source}
                </Badge>
              )}
              {segment.metadata.extras?.rank && (
                <Badge variant="outline" className="text-xs">
                  Rank: {segment.metadata.extras.rank}
                </Badge>
              )}
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
