"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";

const API =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type SearchMode = "exact" | "semantic";

type TranscriptResult = {
  id: string;
  meeting_id: string;
  speaker: string | null;
  text: string;
  start_time: number;
  end_time: number;
};

type MemoryResult = {
  meeting_id: string;
  content: string;
  similarity: number;
};

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const remaining = total % 60;

  return `${String(minutes).padStart(2, "0")}:${String(
    remaining
  ).padStart(2, "0")}`;
}

export default function MemorySearchPage() {
  const [mode, setMode] = useState<SearchMode>("exact");
  const [query, setQuery] = useState("");
  const [threshold, setThreshold] = useState(0.6);
  const [transcripts, setTranscripts] = useState<TranscriptResult[]>([]);
  const [memories, setMemories] = useState<MemoryResult[]>([]);
  const [total, setTotal] = useState(0);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function changeMode(next: SearchMode) {
    setMode(next);
    setTranscripts([]);
    setMemories([]);
    setTotal(0);
    setSearched(false);
    setError("");
  }

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const text = query.trim();
    if (!text || loading) return;

    setLoading(true);
    setError("");
    setSearched(false);
    setTranscripts([]);
    setMemories([]);
    setTotal(0);

    try {
      if (mode === "exact") {
        const params = new URLSearchParams({
          q: text,
          limit: "50",
        });

        const response = await fetch(
          `${API}/api/transcripts/search?${params.toString()}`
        );

        if (!response.ok) {
          throw new Error(`Transcript search failed (${response.status})`);
        }

        const data: {
          total: number;
          results: TranscriptResult[];
        } = await response.json();

        setTranscripts(data.results);
        setTotal(data.total);
      } else {
        const response = await fetch(`${API}/api/memory/search`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            query: text,
            limit: 20,
            similarity_threshold: threshold,
          }),
        });

        if (!response.ok) {
          throw new Error(`Memory search failed (${response.status})`);
        }

        const data: {
          total: number;
          results: MemoryResult[];
        } = await response.json();

        setMemories(data.results);
        setTotal(data.total);
      }

      setSearched(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Search failed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        maxWidth: 900,
        margin: "0 auto",
        padding: "48px 24px",
      }}
    >
      <Link href="/">← Back to Dashboard</Link>

      <h1 style={{ marginTop: 32 }}>Meeting Intelligence Search</h1>

      <p>Find information across your recorded meetings.</p>

      <div style={{ display: "flex", gap: 12, marginTop: 24 }}>
        <button
          type="button"
          onClick={() => changeMode("exact")}
          aria-pressed={mode === "exact"}
          style={{
            padding: "12px 18px",
            borderRadius: 8,
            background: mode === "exact" ? "#222" : "#ddd",
            color: mode === "exact" ? "#fff" : "#222",
          }}
        >
          Exact Transcript
        </button>

        <button
          type="button"
          onClick={() => changeMode("semantic")}
          aria-pressed={mode === "semantic"}
          style={{
            padding: "12px 18px",
            borderRadius: 8,
            background: mode === "semantic" ? "#222" : "#ddd",
            color: mode === "semantic" ? "#fff" : "#222",
          }}
        >
          Semantic Memory
        </button>
      </div>

      <form onSubmit={handleSearch} style={{ marginTop: 28 }}>
        <label htmlFor="search-query">
          {mode === "exact"
            ? "Search transcript text or speaker"
            : "Search meeting memory"}
        </label>

        <textarea
          id="search-query"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={
            mode === "exact"
              ? "Eric Johnson"
              : "What did we decide about project deadlines?"
          }
          maxLength={mode === "exact" ? 500 : 2000}
          rows={3}
          required
          style={{
            display: "block",
            width: "100%",
            padding: 14,
            marginTop: 12,
            border: "1px solid #aaa",
            borderRadius: 10,
            background: "transparent",
            color: "inherit",
          }}
        />

        {mode === "semantic" && (
          <div style={{ marginTop: 20 }}>
            <label htmlFor="threshold">
              Minimum similarity: {Math.round(threshold * 100)}%
            </label>

            <input
              id="threshold"
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={threshold}
              onChange={(event) =>
                setThreshold(Number(event.target.value))
              }
              style={{
                display: "block",
                width: "100%",
                marginTop: 12,
              }}
            />
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !query.trim()}
          style={{
            marginTop: 20,
            padding: "12px 24px",
            borderRadius: 10,
            background: "#222",
            color: "#fff",
          }}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {error && (
        <p role="alert" style={{ color: "#d33", marginTop: 24 }}>
          {error}
        </p>
      )}

      {searched && (
        <section style={{ marginTop: 36 }} aria-live="polite">
          <h2>{total} results</h2>

          {total === 0 && (
            <p>No matches found. Try another search term.</p>
          )}

          {mode === "exact" &&
            transcripts.map((result) => (
              <article
                key={result.id}
                style={{
                  padding: 20,
                  border: "1px solid #ccc",
                  borderRadius: 12,
                  marginTop: 16,
                }}
              >
                <strong>{result.speaker || "Unknown speaker"}</strong>

                <p>
                  {formatTime(result.start_time)} –{" "}
                  {formatTime(result.end_time)}
                </p>

                <p style={{ whiteSpace: "pre-wrap" }}>
                  {result.text}
                </p>

                <Link href={`/meetings/${result.meeting_id}`}>
                  View original meeting →
                </Link>
              </article>
            ))}

          {mode === "semantic" &&
            memories.map((result, index) => (
              <article
                key={`${result.meeting_id}-${index}`}
                style={{
                  padding: 20,
                  border: "1px solid #ccc",
                  borderRadius: 12,
                  marginTop: 16,
                }}
              >
                <strong>
                  Similarity: {Math.round(result.similarity * 100)}%
                </strong>

                <p style={{ whiteSpace: "pre-wrap" }}>
                  {result.content}
                </p>

                <Link href={`/meetings/${result.meeting_id}`}>
                  View original meeting →
                </Link>
              </article>
            ))}
        </section>
      )}
    </main>
  );
}
