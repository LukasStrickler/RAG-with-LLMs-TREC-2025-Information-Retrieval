"use client";

import { ArrowLeft } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { getDocument } from "@/lib/api";

interface Document {
  title: string;
  body: string;
  url: string;
  length: number;
}

export default function DocumentPage() {
  const params = useParams();
  const router = useRouter();
  const [document, setDocument] = useState<Document | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDocument = async () => {
      if (!params.id) return;

      try {
        setLoading(true);
        const doc = await getDocument(params.id as string);
        setDocument(doc as Document);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load document",
        );
      } finally {
        setLoading(false);
      }
    };

    fetchDocument();
  }, [params.id]);

  if (loading) {
    return (
      <div className="container mx-auto py-8 px-4 flex justify-center items-center min-h-[50vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-8 px-4">
        <Button variant="ghost" onClick={() => router.back()} className="mb-4">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Search
        </Button>
        <div className="bg-destructive/10 text-destructive p-4 rounded-md">
          Error: {error}
        </div>
      </div>
    );
  }

  if (!document) {
    return (
      <div className="container mx-auto py-8 px-4">
        <Button variant="ghost" onClick={() => router.back()} className="mb-4">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back to Search
        </Button>
        <div className="text-muted-foreground">Document not found</div>
      </div>
    );
  }

  return (
    <div className="container mx-auto py-8 px-4 max-w-4xl">
      <Button variant="ghost" onClick={() => router.back()} className="mb-4">
        <ArrowLeft className="mr-2 h-4 w-4" /> Back to Search
      </Button>

      <article className="prose prose-slate dark:prose-invert max-w-none">
        <h1 className="text-3xl font-bold mb-4">{document.title}</h1>

        {document.url && (
          <div className="mb-6">
            <a
              href={document.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary hover:underline break-all"
            >
              {document.url}
            </a>
          </div>
        )}

        <div className="bg-card border rounded-lg p-6 shadow-sm">
          <div className="whitespace-pre-wrap font-sans text-lg leading-relaxed">
            {document.body}
          </div>
        </div>

        <div className="mt-8 text-sm text-muted-foreground border-t pt-4">
          <p>Document Length: {document.length} characters</p>
        </div>
      </article>
    </div>
  );
}
