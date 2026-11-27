"use client";

import { FormEvent, useState, useEffect, useCallback } from "react";
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

type Meeting = {
  id: string;
  title: string;
  created_at: string | null;
};

type MemorySearchResponse = {
  query: string;
  results: MemoryResult[];
  total: number;
};

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds));
  const minutes = Math.floor(total / 60);
  const remaining = total % 60;

  return `${String(minutes).padStart(2, "0")}:${String(
    remaining
  ).padStart(2, "0")}`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "Unknown date";
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "Unknown date";
  }
}

export default function MemorySearchPage() {
  const [mode, setMode] = useState<SearchMode>("semantic");
  const [query, setQuery] = useState("");
  const [threshold, setThreshold] = useState(0.7);
  const [meetingId, setMeetingId] = useState("");
  const [resultType, setResultType] = useState("all");
  const [transcripts, setTranscripts] = useState<TranscriptResult[]>([]);
  const [memories, setMemories] = useState<MemoryResult[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [total, setTotal] = useState(0);
  const [searched, setSearched] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadMeetings = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/meetings?page=1&page_size=100`, { cache: "no-store" });
      if (response.ok) {
        const data = await response.json();
        const items = Array.isArray(data) ? data : data.items ?? data.meetings ?? [];
        setMeetings(items);
      }
    } catch (err) {
      console.error('Failed to load meetings:', err);
    }
  }, []);

  useEffect(() => {
    void loadMeetings();
  }, [loadMeetings]);

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
        const params = new URLSearchParams({
          q: text,
          limit: String(20),
          similarity_threshold: String(threshold),
        });
        if (meetingId) params.append("meeting_id", meetingId);
        if (resultType !== "all") params.append("result_type", resultType);

        const response = await fetch(`${API}/api/memory/search?${params.toString()}`);

        if (!response.ok) {
          throw new Error(`Memory search failed (${response.status})`);
        }

        const data: MemorySearchResponse = await response.json();

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

  // Find meeting title for a meeting_id
  function getMeetingTitle(meetingId: string): string {
    const meeting = meetings.find(m => m.id === meetingId);
    return meeting ? meeting.title : "Unknown meeting";
  }

  // Find meeting date for a meeting_id
  function getMeetingDate(meetingId: string): string {
    const meeting = meetings.find(m => m.id === meetingId);
    return meeting ? formatDate(meeting.created_at) : "";
  }

  return (
    <main className="page-wrapper">
      <Link href="/" className="back-link">
        ← Dashboard
      </Link>

      <h1>Meeting Memory Search</h1>

      <p className="text-slate-500">
        Search across meetings, transcripts, decisions, and commitments using keyword or semantic search.
      </p>

      {/* Mode Tabs */}
      <div role="tablist" aria-label="Search mode" style={{ marginTop: 24, display: "flex", borderBottom: "1px solid #e2e8f0" }}>
        <button
          role="tab"
          aria-selected={mode === "exact"}
          onClick={() => changeMode("exact")}
          className={`mode-tab ${mode === "exact" ? "active" : ""}`}
          style={{
            padding: "14px 24px",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            fontSize: 15,
            fontWeight: 600,
            color: mode === "exact" ? "#1e293b" : "#64748b",
            borderBottom: mode === "exact" ? "3px solid #2563eb" : "3px solid transparent",
            marginBottom: "-1px",
            transition: "color 0.2s, border-color 0.2s",
          }}
        >
          Transcript Search
        </button>
        <button
          role="tab"
          aria-selected={mode === "semantic"}
          onClick={() => changeMode("semantic")}
          className={`mode-tab ${mode === "semantic" ? "active" : ""}`}
          style={{
            padding: "14px 24px",
            border: "none",
            background: "transparent",
            cursor: "pointer",
            fontSize: 15,
            fontWeight: 600,
            color: mode === "semantic" ? "#1e293b" : "#64748b",
            borderBottom: mode === "semantic" ? "3px solid #2563eb" : "3px solid transparent",
            marginBottom: "-1px",
            transition: "color 0.2s, border-color 0.2s",
          }}
        >
          Memory Search
        </button>
      </div>

      <form onSubmit={handleSearch} style={{ marginTop: 28 }}>
        <div style={{ display: "grid", gap: 16, marginBottom: 16 }}>
          <div>
            <label htmlFor="search-query" style={{ display: "block", marginBottom: 8, fontWeight: 500 }}>
              {mode === "exact"
                ? "Search transcript text or speaker"
                : "Search meeting memory (decisions, commitments, summaries)"}
            </label>

            <textarea
              id="search-query"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={
                mode === "exact"
                  ? "e.g., Eric Johnson"
                  : "e.g., What did we decide about project deadlines?"
              }
              maxLength={mode === "exact" ? 500 : 2000}
              rows={3}
              required
              className="meeting-search"
              style={{ minHeight: 100 }}
            />
          </div>

          {mode === "semantic" && (
            <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))" }}>
              <div>
                <label htmlFor="meeting-filter" style={{ display: "block", marginBottom: 8, fontWeight: 500 }}>
                  Filter by Meeting
                </label>
                <select
                  id="meeting-filter"
                  value={meetingId}
                  onChange={(event) => setMeetingId(event.target.value)}
                  className="meeting-search"
                >
                  <option value="">All meetings</option>
                  {meetings.map((meeting) => (
                    <option key={meeting.id} value={meeting.id}>
                      {meeting.title}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label htmlFor="type-filter" style={{ display: "block", marginBottom: 8, fontWeight: 500 }}>
                  Result Type
                </label>
                <select
                  id="type-filter"
                  value={resultType}
                  onChange={(event) => setResultType(event.target.value)}
                  className="meeting-search"
                >
                  <option value="all">All types</option>
                  <option value="commitment">Commitments</option>
                  <option value="decision">Decisions</option>
                  <option value="summary">Summaries</option>
                  <option value="transcript">Transcripts</option>
                </select>
              </div>

              <div>
                <label htmlFor="threshold" style={{ display: "block", marginBottom: 8, fontWeight: 500 }}>
                  Minimum Similarity: {Math.round(threshold * 100)}%
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
                    marginTop: 8,
                  }}
                />
              </div>
            </div>
          )}
        </div>

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className="primary-button"
          style={{ padding: "14px 28px" }}
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </form>

      {error && (
        <p role="alert" className="meeting-alert meeting-alert-error" style={{ marginTop: 24 }}>
          {error}
        </p>
      )}

      {searched && (
        <section style={{ marginTop: 36 }} aria-live="polite">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <h2 style={{ fontSize: 20, fontWeight: 600 }}>
              {total} result{total !== 1 ? "s" : ""} found
            </h2>
            {mode === "semantic" && (
              <p style={{ fontSize: 14, color: "#64748b" }}>
                Showing semantic memory results
              </p>
            )}
          </div>

          {total === 0 && (
            <div style={{ padding: 48, textAlign: "center", border: "1px dashed #cbd5e1", borderRadius: 12 }}>
              <p style={{ fontSize: 18, color: "#64748b", marginBottom: 8 }}>
                No matches found
              </p>
              <p style={{ color: "#94a3b8" }}>
                Try adjusting your search terms, filters, or similarity threshold.
              </p>
            </div>
          )}

          {mode === "exact" &&
            transcripts.map((result) => (
              <article
                key={result.id}
                className="meeting-card"
                style={{ marginTop: 16 }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
                  <div>
                    <strong style={{ fontSize: 16 }}>{result.speaker || "Unknown speaker"}</strong>
                    <span style={{ marginLeft: 12, color: "#64748b", fontSize: 14 }}>
                      {formatTime(result.start_time)} – {formatTime(result.end_time)}
                    </span>
                  </div>
                  <Link
                    href={`/meetings/${result.meeting_id}`}
                    className="primary-button"
                    style={{ padding: "8px 14px", fontSize: 14 }}
                  >
                    View Meeting →
                  </Link>
                </div>

                <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, color: "#1e293b" }}>
                  {result.text}
                </p>

                <p style={{ marginTop: 12, fontSize: 13, color: "#94a3b8" }}>
                  Meeting: <Link href={`/meetings/${result.meeting_id}`} style={{ color: "#2563eb" }}>{getMeetingTitle(result.meeting_id)}</Link> • {getMeetingDate(result.meeting_id)}
                </p>
              </article>
            ))}

          {mode === "semantic" &&
            memories.map((result, index) => (
              <article
                key={`${result.meeting_id}-${index}`}
                className="meeting-card"
                style={{ marginTop: 16 }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12, flexWrap: "wrap", gap: 8 }}>
                  <div>
                    <span style={{
                      display: "inline-block",
                      padding: "4px 10px",
                      borderRadius: 6,
                      background: "#dbeafe",
                      color: "#1d4ed8",
                      fontSize: 12,
                      fontWeight: 600,
                      marginBottom: 8,
                    }}>
                      Similarity: {Math.round(result.similarity * 100)}%
                    </span>
                  </div>
                  <Link
                    href={`/meetings/${result.meeting_id}`}
                    className="primary-button"
                    style={{ padding: "8px 14px", fontSize: 14 }}
                  >
                    View Meeting →
                  </Link>
                </div>

                <p style={{ whiteSpace: "pre-wrap", lineHeight: 1.7, color: "#1e293b", marginBottom: 12 }}>
                  {result.content}
                </p>

                <p style={{ fontSize: 13, color: "#94a3b8" }}>
                  Meeting: <Link href={`/meetings/${result.meeting_id}`} style={{ color: "#2563eb" }}>{getMeetingTitle(result.meeting_id)}</Link> • {getMeetingDate(result.meeting_id)}
                </p>
              </article>
            ))}
        </section>
      )}
    </main>
  );
}