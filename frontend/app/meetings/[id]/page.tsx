"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000/api";

type Meeting = {
  id: string;
  title: string;
  description?: string | null;
  meeting_type?: string | null;
  status?: string | null;
  processing_stage?: string | null;
  duration_seconds?: number | null;
  summary?: string | null;
  original_filename?: string | null;
  created_at?: string | null;
};

type MeetingProcessingStatus = {
  meeting_id: string;
  status: string;
  processing_stage: string;
  duration_seconds?: number | null;
};

type TranscriptSegment = {
  id: string;
  meeting_id: string;
  speaker_label?: string | null;
  speaker_name?: string | null;
  text: string;
  start_time: number;
  end_time: number;
  sequence_number: number;
};

type TranscriptResponse = {
  meeting_id: string;
  segments: TranscriptSegment[];
  total_segments: number;
  duration_seconds?: number | null;
};

type Decision = {
  id: string;
  meeting_id?: string;
  title: string;
  description: string;
  status: string;
  confidence: number;
  changed_from_decision_id?: string | null;
  created_at?: string | null;
};

type Commitment = {
  id: string;
  meeting_id?: string;
  task: string;
  owner_id?: string | null;
  deadline?: string | null;
  deadline_text?: string | null;
  strength: string;
  status: string;
  confidence: number;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

type Evidence = {
  id: string;
  meeting_id?: string;
  transcript_segment_id?: string | null;
  commitment_id?: string | null;
  decision_id?: string | null;
  evidence_type: string;
  snippet: string;
  confidence: number;
  created_at?: string | null;
};

type AnalysisResult = {
  meeting_id: string;
  summary: string;
  key_topics: string[];
  decisions: Decision[];
  commitments: Commitment[];
  evidence: Evidence[];
  overall_confidence: number;
  processing_status: string;
};

type Tab = "overview" | "transcript" | "actions" | "evidence";

type PageProps = {
  params: Promise<{ id: string }>;
};

async function getJson<T>(
  url: string,
  options?: RequestInit
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (body?.detail) message = body.detail;
    } catch {
      // Keep the fallback error message.
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

function formatTime(seconds: number): string {
  const total = Math.max(0, Math.floor(seconds || 0));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remaining = total % 60;
  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(
      minutes
    ).padStart(2, "0")}:${String(remaining).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(
    remaining
  ).padStart(2, "0")}`;
}

function formatDuration(seconds?: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) {
    return "Not available";
  }
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const remaining = total % 60;
  if (hours > 0) return `${hours}h ${minutes}m`;
  if (minutes > 0) return `${minutes}m ${remaining}s`;
  return `${remaining}s`;
}

function titleCase(value?: string | null): string {
  if (!value) return "Unknown";
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function confidencePercent(value?: number | null): string {
  const safe = Math.max(0, Math.min(1, value ?? 0));
  return `${Math.round(safe * 100)}%`;
}

function formatDate(value?: string | null): string {
  if (!value) return "Date unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function Panel({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="meeting-card" style={{ marginTop: 24 }}>
      <div className="meeting-card-heading">
        <div>
          <h2>{title}</h2>
        </div>
      </div>
      {description && (
        <p className="text-sm text-slate-500" style={{ marginTop: 8 }}>
          {description}
        </p>
      )}
      <div style={{ marginTop: 16 }}>{children}</div>
    </section>
  );
}

function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div style={{ border: "1px dashed #cbd5e1", borderRadius: 12, padding: 40, textAlign: "center" }}>
      <p style={{ fontWeight: 500, color: "#334155" }}>{title}</p>
      <p style={{ marginTop: 8, fontSize: 14, color: "#64748b" }}>
        {description}
      </p>
    </div>
  );
}

const PROCESSING_STAGES = [
  { id: "queued", label: "Queued", description: "Your recording is waiting to be processed." },
  { id: "transcribing", label: "Transcribing audio", description: "Converting the recording into text." },
  { id: "identifying_speakers", label: "Identifying speakers", description: "Matching transcript segments to speakers." },
  { id: "saving_transcript", label: "Saving transcript", description: "Saving the transcript and speaker labels." },
  { id: "transcription_completed", label: "Transcript ready", description: "Transcript saved; meeting analysis is next." },
  { id: "analyzing", label: "Analyzing meeting", description: "Extracting the summary, decisions, commitments, and evidence." },
  { id: "completed", label: "Completed", description: "Processing finished and results are ready." },
] as const;

function normalizedStage(meeting: Meeting): string {
  if (meeting.status?.toLowerCase() === "completed") return "completed";
  if (meeting.status?.toLowerCase() === "failed") return "failed";
  return (meeting.processing_stage || "uploaded").toLowerCase();
}

function ProcessingProgress({ meeting }: { meeting: Meeting }) {
  const stage = normalizedStage(meeting);
  const failed = stage === "failed";
  const currentIndex = PROCESSING_STAGES.findIndex((item) => item.id === stage);
  const activeIndex = stage === "uploaded" ? -1 : currentIndex;
  const isWorking =
    !failed &&
    meeting.status?.toLowerCase() !== "completed" &&
    (meeting.status?.toLowerCase() === "processing" ||
      ["queued", "transcribing", "identifying_speakers", "saving_transcript", "transcription_completed", "analyzing"].includes(stage));

  if (!isWorking && !failed && stage !== "completed") return null;

  return (
    <section className="meeting-card" style={{ marginTop: 24 }}>
      <div className="meeting-card-heading">
        <div>
          <span className="eyebrow">PROCESSING</span>
          <h2>{failed ? "Processing failed" : stage === "completed" ? "Meeting ready" : "Meeting processing"}</h2>
        </div>
        <span style={{ padding: "4px 10px", borderRadius: 9999, fontSize: 12, fontWeight: 600, background: failed ? "#fef2f2" : stage === "completed" ? "#dcfce7" : "#dbeafe", color: failed ? "#991b1b" : stage === "completed" ? "#166534" : "#1d4ed8" }}>
          {failed ? "Failed" : stage === "completed" ? "Completed" : "In progress"}
        </span>
      </div>

      <p style={{ marginTop: 8, fontSize: 14, color: "#64748b" }}>
        {failed
          ? "The backend could not finish processing this recording. Check the backend logs, then retry or refresh."
          : stage === "completed"
          ? "Your transcript and meeting results are ready."
          : "This page checks the backend automatically and updates as the recording moves through each stage."}
      </p>

      {!failed && (
        <>
          <div style={{ marginTop: 16, height: 8, borderRadius: 9999, background: "#e2e8f0", overflow: "hidden" }}>
            <div
              className="h-full rounded-full bg-blue-600 transition-all duration-500"
              style={{ width: `${stage === "completed" ? 100 : Math.max(5, ((Math.max(activeIndex, 0) + 1) / PROCESSING_STAGES.length) * 100)}%` }}
            />
          </div>
          <div style={{ marginTop: 16, display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))" }}>
            {PROCESSING_STAGES.map((item, index) => {
              const done = stage === "completed" || (activeIndex >= 0 && index < activeIndex);
              const active = item.id === stage;
              return (
                <div key={item.id} style={{ border: "1px solid", padding: 16, borderRadius: 12, borderColor: active ? "#3b82f6" : done ? "#22c55e" : "#e2e8f0", background: active ? "#eff6ff" : done ? "#dcfce7" : "#fff" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                    <span style={{ width: 24, height: 24, borderRadius: 9999, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, background: done ? "#16a34a" : active ? "#3b82f6" : "#e2e8f0", color: done || active ? "#fff" : "#94a3b8" }}>
                      {done ? "✓" : index + 1}
                    </span>
                    <span style={{ padding: "4px 10px", borderRadius: 9999, fontSize: 13, fontWeight: 600, background: "#dbeafe", color: "#1d4ed8" }}>{item.label}</span>
                  </div>
                  <p style={{ fontSize: 12, color: "#64748b" }}>{item.description}</p>
                </div>
              );
            })}
          </div>
        </>
      )}
    </section>
  );
}

export default function MeetingDetailsPage({ params }: PageProps) {
  const [meetingId, setMeetingId] = useState<string | null>(null);
  const [meeting, setMeeting] = useState<Meeting | null>(null);
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([]);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [backendOnline, setBackendOnline] = useState(false);
  const [error, setError] = useState("");
  const [transcriptSearch, setTranscriptSearch] = useState("");
  const [actionSearch, setActionSearch] = useState("");

  // Resolve the dynamic Next.js route parameter.
  useEffect(() => {
    let cancelled = false;
    params
      .then(({ id }) => {
        if (!cancelled) setMeetingId(id);
      })
      .catch(() => {
        if (!cancelled) {
          setError("Unable to read the meeting ID.");
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [params]);

  // Load meeting metadata, transcript, and SAVED analysis.
  const loadMeeting = useCallback(async (id: string) => {
    setError("");
    try {
      const [meetingData, transcriptData] = await Promise.all([
        getJson<Meeting>(
          `${API_BASE}/meetings/${encodeURIComponent(id)}`
        ),
        getJson<TranscriptResponse>(
          `${API_BASE}/transcription/${encodeURIComponent(id)}`
        ),
      ]);
      setMeeting(meetingData);
      setTranscript(transcriptData.segments || []);
      setBackendOnline(true);
      // This is a GET request. It must not rerun AI analysis.
      try {
        const savedAnalysis = await getJson<AnalysisResult>(
          `${API_BASE}/analysis/meetings/${encodeURIComponent(
            id
          )}/summary`
        );
        setAnalysis({
          meeting_id: savedAnalysis.meeting_id || id,
          summary: savedAnalysis.summary || "",
          key_topics: savedAnalysis.key_topics || [],
          decisions: savedAnalysis.decisions || [],
          commitments: savedAnalysis.commitments || [],
          evidence: savedAnalysis.evidence || [],
          overall_confidence: savedAnalysis.overall_confidence ?? 0,
          processing_status:
            savedAnalysis.processing_status || "completed",
        });
      } catch (analysisError) {
        // A meeting may exist before it has been analysed.
        console.warn("Could not load saved analysis:", analysisError);
        setAnalysis(null);
      }
    } catch (loadError) {
      console.error("Meeting loading error:", loadError);
      setBackendOnline(false);
      setError(
        loadError instanceof Error
          ? loadError.message
          : "Failed to load meeting."
      );
    }
  }, []);

  useEffect(() => {
    if (!meetingId) return;
    let cancelled = false;
    async function initialLoad() {
      setLoading(true);
      await loadMeeting(meetingId!);
      if (!cancelled) setLoading(false);
    }
    void initialLoad();
    return () => {
      cancelled = true;
    };
  }, [meetingId, loadMeeting]);

  // Poll the backend while processing, then reload persisted transcript and analysis.
  useEffect(() => {
    if (!meetingId || !meeting) return;

    const currentStage = normalizedStage(meeting);
    const isTerminal =
      meeting.status?.toLowerCase() === "completed" ||
      meeting.status?.toLowerCase() === "failed" ||
      currentStage === "completed" ||
      currentStage === "failed";

    if (isTerminal) return;

    let cancelled = false;
    let finalReloadStarted = false;

    const pollStatus = async () => {
      try {
        const statusData = await getJson<MeetingProcessingStatus>(
          `${API_BASE}/meetings/${encodeURIComponent(meetingId)}/status`
        );
        if (cancelled) return;

        setMeeting((previous) =>
          previous
            ? {
                ...previous,
                status: statusData.status || previous.status,
                processing_stage: statusData.processing_stage || previous.processing_stage,
                duration_seconds: statusData.duration_seconds ?? previous.duration_seconds,
              }
            : previous
        );
        setBackendOnline(true);

        const status = (statusData.status || "").toLowerCase();
        const stage = (statusData.processing_stage || "").toLowerCase();
        if (
          !finalReloadStarted &&
          (status === "completed" || status === "failed" || stage === "completed" || stage === "failed")
        ) {
          finalReloadStarted = true;
          await loadMeeting(meetingId);
        }
      } catch (pollError) {
        if (!cancelled) {
          console.warn("Could not refresh processing status:", pollError);
        }
      }
    };

    void pollStatus();
    const intervalId = window.setInterval(() => {
      void pollStatus();
    }, 2500);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [meetingId, meeting?.status, meeting?.processing_stage, loadMeeting]);

  const refreshMeeting = async () => {
    if (!meetingId) return;
    setRefreshing(true);
    await loadMeeting(meetingId);
    setRefreshing(false);
  };

  // Run AI only when the user explicitly requests analysis.
  const analyzeMeeting = async () => {
    if (!meetingId || analyzing) return;
    setAnalyzing(true);
    setError("");
    try {
      const result = await getJson<AnalysisResult>(
        `${API_BASE}/analysis/meetings/${encodeURIComponent(
          meetingId
        )}`,
        { method: "POST" }
      );
      setAnalysis(result);
      // Reload from the database after the analysis finishes.
      await loadMeeting(meetingId);
    } catch (analysisError) {
      console.error("Analysis error:", analysisError);
      setError(
        analysisError instanceof Error
          ? analysisError.message
          : "Meeting analysis failed."
      );
    } finally {
      setAnalyzing(false);
    }
  };

  const decisions = analysis?.decisions || [];
  const commitments = analysis?.commitments || [];
  const evidence = analysis?.evidence || [];
  const keyTopics = analysis?.key_topics || [];
  const filteredTranscript = transcript.filter((segment) => {
    const query = transcriptSearch.trim().toLowerCase();
    if (!query) return true;
    return (
      segment.text.toLowerCase().includes(query) ||
      (segment.speaker_name || "").toLowerCase().includes(query) ||
      (segment.speaker_label || "").toLowerCase().includes(query)
    );
  });
  const filteredCommitments = commitments.filter((item) => {
    const query = actionSearch.trim().toLowerCase();
    if (!query) return true;
    return (
      item.task.toLowerCase().includes(query) ||
      (item.notes || "").toLowerCase().includes(query) ||
      (item.deadline_text || "").toLowerCase().includes(query) ||
      item.status.toLowerCase().includes(query)
    );
  });

  if (loading) {
    return (
      <main className="page-wrapper" style={{ minHeight: "calc(100vh - 200px)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ border: "1px solid #e2e8f0", borderRadius: 16, padding: 40, textAlign: "center" }}>
          <div style={{ margin: "0 auto 16px", width: 32, height: 32, border: "2px solid #e2e8f0", borderTopColor: "#3b82f6", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
          <p style={{ fontWeight: 500, color: "#334155" }}>Loading meeting and saved results...</p>
        </div>
        <style jsx>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </main>
    );
  }

  if (!meeting) {
    return (
      <main className="page-wrapper" style={{ minHeight: "calc(100vh - 200px)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{ maxWidth: 400, border: "1px solid #e2e8f0", borderRadius: 16, padding: 32, textAlign: "center" }}>
          <h1 style={{ fontSize: 20, fontWeight: 600, color: "#1e293b" }}>Meeting unavailable</h1>
          <p style={{ marginTop: 12, fontSize: 14, color: "#64748b" }}>
            {error || "The meeting could not be loaded."}
          </p>
          <button
            onClick={() => window.history.back()}
            className="primary-button"
            style={{ marginTop: 24 }}
          >
            Go back
          </button>
        </div>
      </main>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "transcript", label: "Transcript" },
    { id: "actions", label: "Decisions & Actions" },
    { id: "evidence", label: "Evidence" },
  ];

  return (
    <main className="page-wrapper" style={{ minHeight: "calc(100vh - 200px)" }}>
      <header style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: 16, marginBottom: 16 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8, fontSize: 12, fontWeight: 500, color: "#64748b", marginBottom: 8 }}>
              <Link href="/" className="back-link" style={{ color: "#64748b" }}>
                Dashboard
              </Link>
              <span>/</span>
              <span>Meeting details</span>
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 12 }}>
              <h1 style={{ fontSize: 28, fontWeight: 700 }}>{meeting.title}</h1>
              <span style={{ padding: "4px 10px", borderRadius: 9999, border: "1px solid #e2e8f0", background: "#fff", fontSize: 12, fontWeight: 500, color: "#475569" }}>
                {titleCase(meeting.status)}
              </span>
            </div>
            <p style={{ marginTop: 12, maxWidth: "800px", fontSize: 14, color: "#64748b" }}>
              {meeting.description ||
                meeting.original_filename ||
                "Meeting intelligence, decisions, and accountability."}
            </p>
            <div style={{ marginTop: 12, display: "flex", flexWrap: "wrap", gap: 20, fontSize: 12, color: "#64748b" }}>
              <span>{formatDate(meeting.created_at)}</span>
              <span>{formatDuration(meeting.duration_seconds)}</span>
              <span>{transcript.length} transcript segments</span>
              <span>{backendOnline ? "Backend connected" : "Backend unavailable"}</span>
            </div>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            <Link
              href={`/chat?meeting_id=${encodeURIComponent(String(meeting.id))}`}
              className="primary-button"
              style={{ background: "#7c3aed", padding: "10px 16px", fontSize: 14 }}
            >
              ✦ Ask AI
            </Link>
            <button
              onClick={() => void refreshMeeting()}
              disabled={refreshing}
              className="primary-button"
              style={{ background: "transparent", border: "1px solid #cbd5e1", color: "#374151", padding: "10px 16px", fontSize: 14 }}
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
            <button
              onClick={() => void analyzeMeeting()}
              disabled={analyzing || !transcript.length}
              className="primary-button"
              style={{ padding: "10px 16px", fontSize: 14 }}
            >
              {analyzing
                ? "Analysing meeting..."
                : analysis?.summary
                  ? "Reanalyse meeting"
                  : "Analyse meeting"}
            </button>
          </div>
        </div>
      </header>

      {error && (
        <p role="alert" className="meeting-alert meeting-alert-error" style={{ marginBottom: 24 }}>
          {error}
        </p>
      )}

      <ProcessingProgress meeting={meeting} />

      {/* Metrics */}
      <section style={{ marginTop: 24, display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
        {[
          {
            label: "Decisions",
            value: decisions.length,
            detail: "Recorded outcomes",
          },
          {
            label: "Commitments",
            value: commitments.length,
            detail: "Actionable items",
          },
          {
            label: "Evidence",
            value: evidence.length,
            detail: "Supporting excerpts",
          },
          {
            label: "AI confidence",
            value: confidencePercent(analysis?.overall_confidence),
            detail: "Extraction confidence",
          },
        ].map((metric) => (
          <div
            key={metric.label}
            style={{ border: "1px solid #e2e8f0", borderRadius: 16, padding: 20, background: "#fff" }}
          >
            <p style={{ fontSize: 11, fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.05em", color: "#64748b" }}>
              {metric.label}
            </p>
            <p style={{ marginTop: 12, fontSize: 28, fontWeight: 700, color: "#1e293b" }}>
              {metric.value}
            </p>
            <p style={{ marginTop: 4, fontSize: 11, color: "#94a3b8" }}>
              {metric.detail}
            </p>
          </div>
        ))}
      </section>

      {/* Navigation */}
      <nav style={{ marginTop: 24, display: "flex", gap: 4, overflowX: "auto", border: "1px solid #e2e8f0", borderRadius: 12, padding: 4, background: "#fff" }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flexShrink: 0,
              padding: "10px 16px",
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 500,
              cursor: "pointer",
              background: activeTab === tab.id ? "#3b82f6" : "transparent",
              color: activeTab === tab.id ? "#fff" : "#475569",
              border: "none",
              transition: "all 0.2s",
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      {/* Overview */}
      {activeTab === "overview" && (
        <div style={{ marginTop: 24, display: "grid", gap: 24, gridTemplateColumns: "1fr" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <Panel
              title="Meeting summary"
              description="The summary saved for this meeting."
            >
              {analysis?.summary ? (
                <p style={{ whiteSpace: "pre-wrap", fontSize: 14, lineHeight: 1.7, color: "#334155" }}>
                  {analysis.summary}
                </p>
              ) : (
                <EmptyState
                  title="No saved summary yet"
                  description="Run analysis once to generate a summary. After it is saved, this page will load it automatically."
                />
              )}
            </Panel>
            <Panel
              title="Key topics"
              description="Main subjects identified during analysis."
            >
              {keyTopics.length > 0 ? (
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {keyTopics.map((topic, index) => (
                    <span
                      key={`${topic}-${index}`}
                      style={{ padding: "6px 12px", borderRadius: 9999, border: "1px solid #e2e8f0", background: "#f8fafc", fontSize: 13, color: "#334155" }}
                    >
                      {topic}
                    </span>
                  ))}
                </div>
              ) : (
                <p style={{ fontSize: 14, color: "#64748b" }}>
                  No saved topics are available. The current database
                  does not store the original topic list separately yet.
                </p>
              )}
            </Panel>
            <Panel
              title="Decisions"
              description="Outcomes extracted from the meeting."
            >
              {decisions.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {decisions.slice(0, 5).map((decision) => (
                    <article
                      key={decision.id}
                      style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, background: "#fff" }}
                    >
                      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
                        <h3 style={{ fontWeight: 500, color: "#1e293b" }}>{decision.title}</h3>
                        <span style={{ padding: "4px 10px", borderRadius: 9999, background: "#f1f5f9", fontSize: 11, fontWeight: 500, color: "#475569" }}>
                          {titleCase(decision.status)}
                        </span>
                      </div>
                      <p style={{ fontSize: 13, lineHeight: 1.6, color: "#475569" }}>
                        {decision.description}
                      </p>
                      <p style={{ marginTop: 12, fontSize: 11, color: "#94a3b8" }}>
                        Confidence: {confidencePercent(decision.confidence)}
                      </p>
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="No decisions saved"
                  description="Saved decisions will appear here after analysis."
                />
              )}
            </Panel>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            <Panel
              title="Meeting information"
              description="Details about the recording."
            >
              <dl style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {[
                  ["Meeting type", titleCase(meeting.meeting_type)],
                  ["Status", titleCase(meeting.status)],
                  ["Duration", formatDuration(meeting.duration_seconds)],
                  ["Date created", formatDate(meeting.created_at)],
                  ["Transcript segments", String(transcript.length)],
                  [
                    "Analysis status",
                    titleCase(analysis?.processing_status || "pending"),
                  ],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    style={{ display: "flex", justifyContent: "space-between", paddingBottom: 12, borderBottom: "1px solid #f1f5f9" }}
                  >
                    <dt style={{ fontSize: 13, color: "#64748b" }}>{label}</dt>
                    <dd style={{ fontSize: 13, fontWeight: 500, color: "#1e293b", textAlign: "right" }}>
                      {value}
                    </dd>
                  </div>
                ))}
              </dl>
            </Panel>
            <Panel
              title="Recent commitments"
              description="A quick view of saved action items."
            >
              {commitments.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                  {commitments.slice(0, 5).map((item) => (
                    <div
                      key={item.id}
                      style={{ paddingBottom: 16, borderBottom: "1px solid #f1f5f9" }}
                    >
                      <p style={{ fontSize: 13, fontWeight: 500, color: "#1e293b" }}>
                        {item.task}
                      </p>
                      <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 12, fontSize: 11, color: "#64748b" }}>
                        <span>{titleCase(item.status)}</span>
                        <span>·</span>
                        <span>
                          {item.deadline_text ||
                            (item.deadline
                              ? formatDate(item.deadline)
                              : "No deadline")}
                        </span>
                      </div>
                    </div>
                  ))}
                  {commitments.length > 5 && (
                    <button
                      onClick={() => setActiveTab("actions")}
                      style={{ fontSize: 13, fontWeight: 500, color: "#2563eb" }}
                    >
                      View all {commitments.length} commitments →
                    </button>
                  )}
                </div>
              ) : (
                <EmptyState
                  title="No commitments saved"
                  description="Action items will appear here after analysis."
                />
              )}
            </Panel>
          </div>
        </div>
      )}

      {/* Transcript */}
      {activeTab === "transcript" && (
        <Panel
          title="Meeting transcript"
          description="Search the saved transcript and review speaker-attributed segments."
        >
          <input
            value={transcriptSearch}
            onChange={(event) => setTranscriptSearch(event.target.value)}
            placeholder="Search transcript or speaker..."
            className="meeting-search"
            style={{ marginBottom: 20 }}
          />
          {filteredTranscript.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {filteredTranscript.map((segment) => (
                <article
                  key={segment.id}
                  style={{ border: "1px solid #e2e8f0", borderRadius: 16, padding: 20, background: "#fff", transition: "border-color 0.2s, box-shadow 0.2s" }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#3b82f6"; e.currentTarget.style.boxShadow = "0 4px 12px rgba(0,0,0,0.05)"; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#e2e8f0"; e.currentTarget.style.boxShadow = "none"; }}
                >
                  <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: "#1e293b" }}>
                      {segment.speaker_name ||
                        segment.speaker_label ||
                        "Unknown speaker"}
                    </span>
                    <span style={{ fontFamily: "monospace", fontSize: 11, color: "#64748b" }}>
                      {formatTime(segment.start_time)} –{" "}
                      {formatTime(segment.end_time)}
                    </span>
                  </div>
                  <p style={{ whiteSpace: "pre-wrap", borderLeft: "2px solid #dbeafe", paddingLeft: 16, fontSize: 13, lineHeight: 1.7, color: "#334155" }}>
                    {segment.text}
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No transcript segments found"
              description={
                transcript.length
                  ? "Try another search."
                  : "Transcribe this recording before reviewing the transcript."
              }
            />
          )}
        </Panel>
      )}

      {/* Decisions and commitments */}
      {activeTab === "actions" && (
        <div style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 24 }}>
          <Panel
            title="Decisions"
            description={`${decisions.length} saved decisions`}
          >
            {decisions.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {decisions.map((decision) => (
                  <article
                    key={decision.id}
                    style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, background: "#fff" }}
                  >
                    <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
                      <div style={{ minWidth: 0 }}>
                        <h3 style={{ fontWeight: 600, color: "#1e293b" }}>{decision.title}</h3>
                        <p style={{ marginTop: 8, fontSize: 13, lineHeight: 1.6, color: "#475569" }}>
                          {decision.description}
                        </p>
                      </div>
                      <span style={{ flexShrink: 0, padding: "4px 10px", borderRadius: 9999, background: "#f1f5f9", fontSize: 11, fontWeight: 500, color: "#475569" }}>
                        {titleCase(decision.status)}
                      </span>
                    </div>
                    <div style={{ display: "flex", flexWrap: "wrap", gap: 16, fontSize: 11, color: "#94a3b8" }}>
                      <span>Confidence: {confidencePercent(decision.confidence)}</span>
                      <span>Created: {formatDate(decision.created_at)}</span>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No saved decisions"
                description="Decisions will appear after a successful analysis."
              />
            )}
          </Panel>
          <Panel
            title="Commitments and action items"
            description={`${commitments.length} saved commitments`}
          >
            <input
              value={actionSearch}
              onChange={(event) => setActionSearch(event.target.value)}
              placeholder="Search tasks, deadlines, or status..."
              className="meeting-search"
              style={{ marginBottom: 20 }}
            />
            {filteredCommitments.length > 0 ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                {filteredCommitments.map((item) => (
                  <article
                    key={item.id}
                    style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, background: "#fff" }}
                  >
                    <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <h3 style={{ fontSize: 14, fontWeight: 500, lineHeight: 1.5, color: "#1e293b" }}>
                          {item.task}
                        </h3>
                        {item.notes && (
                          <p style={{ marginTop: 8, fontSize: 13, lineHeight: 1.6, color: "#64748b" }}>
                            {item.notes}
                          </p>
                        )}
                      </div>
                      <span style={{ flexShrink: 0, padding: "4px 10px", borderRadius: 9999, background: "#f1f5f9", fontSize: 11, fontWeight: 500, color: "#475569" }}>
                        {titleCase(item.status)}
                      </span>
                    </div>
                    <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))" }}>
                      <div>
                        <p style={{ fontSize: 11, color: "#94a3b8" }}>Deadline</p>
                        <p style={{ marginTop: 4, fontSize: 13, fontWeight: 500, color: "#1e293b" }}>
                          {item.deadline_text ||
                            (item.deadline
                              ? formatDate(item.deadline)
                              : "Not specified")}
                        </p>
                      </div>
                      <div>
                        <p style={{ fontSize: 11, color: "#94a3b8" }}>Strength</p>
                        <p style={{ marginTop: 4, fontSize: 13, fontWeight: 500, color: "#1e293b" }}>
                          {titleCase(item.strength)}
                        </p>
                      </div>
                      <div>
                        <p style={{ fontSize: 11, color: "#94a3b8" }}>Confidence</p>
                        <p style={{ marginTop: 4, fontSize: 13, fontWeight: 500, color: "#1e293b" }}>
                          {confidencePercent(item.confidence)}
                        </p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <EmptyState
                title="No matching commitments"
                description={
                  commitments.length
                    ? "Try changing your search."
                    : "Saved commitments will appear here after analysis."
                }
              />
            )}
          </Panel>
        </div>
      )}

      {/* Evidence */}
      {activeTab === "evidence" && (
        <Panel
          title="Evidence and source excerpts"
          description="Transcript excerpts linked to extracted decisions and commitments."
        >
          {evidence.length > 0 ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {evidence.map((item) => (
                <article
                  key={item.id}
                  style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 16, background: "#fff" }}
                >
                  <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 8, marginBottom: 12 }}>
                    <span style={{ padding: "4px 10px", borderRadius: 9999, background: "#f1f5f9", fontSize: 11, fontWeight: 500, color: "#334155" }}>
                      {titleCase(item.evidence_type)}
                    </span>
                    <span style={{ fontSize: 11, color: "#94a3b8" }}>
                      Confidence: {confidencePercent(item.confidence)}
                    </span>
                  </div>
                  <blockquote style={{ borderLeft: "2px solid #cbd5e1", paddingLeft: 16, fontSize: 13, lineHeight: 1.7, color: "#334155" }}>
                    {item.snippet}
                  </blockquote>
                  <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 16, fontSize: 11, color: "#94a3b8" }}>
                    {item.transcript_segment_id && <span>Transcript segment linked</span>}
                    {item.decision_id && <span>Decision linked</span>}
                    {item.commitment_id && <span>Commitment linked</span>}
                    <span>{formatDate(item.created_at)}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState
              title="No saved evidence"
              description="Evidence excerpts will appear here when the backend generates and saves them."
            />
          )}
        </Panel>
      )}

      <footer style={{ marginTop: 32, display: "flex", flexDirection: "column", gap: 8, paddingTop: 20, borderTop: "1px solid #e2e8f0", fontSize: 12, color: "#94a3b8" }}>
        <p>Meeting Intelligence & Accountability System</p>
        <p>
          {analysis
            ? "Displaying the analysis returned by the backend."
            : "No saved analysis loaded."}
        </p>
      </footer>
    </main>
  );
}