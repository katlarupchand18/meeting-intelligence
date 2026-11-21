"use client";
import { useCallback, useEffect, useState } from "react";
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
    <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="mb-5">
        <h2 className="text-base font-semibold text-slate-900">
          {title}
        </h2>
        {description && (
          <p className="mt-1 text-sm leading-6 text-slate-500">
            {description}
          </p>
        )}
      </div>
      {children}
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
    <div className="rounded-xl border border-dashed border-slate-200 px-5 py-10 text-center">
      <p className="font-medium text-slate-700">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-500">
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
    <section className="mb-7 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            {failed ? "Processing failed" : stage === "completed" ? "Meeting ready" : "Meeting processing"}
          </h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            {failed
              ? "The backend could not finish processing this recording. Check the backend logs, then retry or refresh."
              : stage === "completed"
                ? "Your transcript and meeting results are ready."
                : "This page checks the backend automatically and updates as the recording moves through each stage."}
          </p>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${
          failed ? "bg-red-100 text-red-700" :
          stage === "completed" ? "bg-emerald-100 text-emerald-700" :
          "bg-blue-100 text-blue-700"
        }`}>
          {failed ? "Failed" : stage === "completed" ? "Completed" : "In progress"}
        </span>
      </div>

      {!failed && (
        <>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-blue-600 transition-all duration-500"
              style={{ width: `${stage === "completed" ? 100 : Math.max(5, ((Math.max(activeIndex, 0) + 1) / PROCESSING_STAGES.length) * 100)}%` }}
            />
          </div>
          <ol className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {PROCESSING_STAGES.map((item, index) => {
              const done = stage === "completed" || (activeIndex >= 0 && index < activeIndex);
              const active = item.id === stage;
              return (
                <li key={item.id} className={`rounded-xl border p-3 ${
                  active ? "border-blue-300 bg-blue-50" :
                  done ? "border-emerald-200 bg-emerald-50" :
                  "border-slate-200 bg-white"
                }`}>
                  <div className="flex items-center gap-2">
                    <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                      done ? "bg-emerald-600 text-white" :
                      active ? "bg-blue-600 text-white" :
                      "bg-slate-100 text-slate-500"
                    }`}>
                      {done ? "✓" : index + 1}
                    </span>
                    <span className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-3 py-1.5 text-sm font-semibold text-blue-700">{item.label}</span>
                  </div>
                  <p className="mt-2 text-xs leading-5 text-slate-500">{item.description}</p>
                </li>
              );
            })}
          </ol>
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
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-5">
        <div className="rounded-2xl border border-slate-200 bg-white px-8 py-7 text-center shadow-sm">
          <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-slate-200 border-t-blue-600" />
          <p className="text-sm font-medium text-slate-700">
            Loading meeting and saved results...
          </p>
        </div>
      </main>
    );
  }
  if (!meeting) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 px-5">
        <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
          <h1 className="text-xl font-semibold text-slate-900">
            Meeting unavailable
          </h1>
          <p className="mt-3 text-sm leading-6 text-slate-500">
            {error || "The meeting could not be loaded."}
          </p>
          <button
            onClick={() => window.history.back()}
            className="mt-6 rounded-xl bg-slate-900 px-5 py-3 text-sm font-medium text-white hover:bg-slate-700"
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
    <main className="meeting-details-workspace min-h-screen min-w-0 flex-1 bg-slate-50 text-slate-900">
      <div className="meeting-details-container mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
        {/* Header */}
        <header className="meeting-details-header mb-7 flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <div className="mb-3 flex flex-wrap items-center gap-2 text-xs font-medium text-slate-500">
              <a href="/" className="hover:text-slate-900">
                Dashboard
              </a>
              <span>/</span>
              <span>Meeting details</span>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="break-words text-2xl font-semibold tracking-tight sm:text-3xl">
                {meeting.title}
              </h1>
              <span className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600">
                {titleCase(meeting.status)}
              </span>
            </div>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-500">
              {meeting.description ||
                meeting.original_filename ||
                "Meeting intelligence, decisions, and accountability."}
            </p>
            <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 text-xs text-slate-500">
              <span>{formatDate(meeting.created_at)}</span>
              <span>{formatDuration(meeting.duration_seconds)}</span>
              <span>
                {transcript.length} transcript segments
              </span>
              <span>
                {backendOnline ? "Backend connected" : "Backend unavailable"}
              </span>
            </div>
          </div>
          <div className="flex shrink-0 flex-wrap gap-2">
            <a
              href={`/chat?meeting_id=${encodeURIComponent(String(meeting.id))}`}
              className="inline-flex items-center rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-violet-700"
            >
              ✦ Ask AI
            </a>
            <button
              onClick={() => void refreshMeeting()}
              disabled={refreshing}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 shadow-sm transition hover:bg-slate-100 disabled:opacity-50"
            >
              {refreshing ? "Refreshing..." : "Refresh"}
            </button>
            <button
              onClick={() => void analyzeMeeting()}
              disabled={analyzing || !transcript.length}
              className="rounded-xl bg-blue-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {analyzing
                ? "Analysing meeting..."
                : analysis?.summary
                  ? "Reanalyse meeting"
                  : "Analyse meeting"}
            </button>
          </div>
        </header>
        {error && (
          <div
            role="alert"
            className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </div>
        )}
        <ProcessingProgress meeting={meeting} />

      {/* Metrics */}
        <section className="meeting-details-metrics mb-7 grid grid-cols-2 gap-3 lg:grid-cols-4">
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
              value: confidencePercent(
                analysis?.overall_confidence
              ),
              detail: "Extraction confidence",
            },
          ].map((metric) => (
            <div
              key={metric.label}
              className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5"
            >
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                {metric.label}
              </p>
              <p className="mt-3 text-2xl font-semibold tracking-tight text-slate-900">
                {metric.value}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {metric.detail}
              </p>
            </div>
          ))}
        </section>
        {/* Navigation */}
        <nav className="meeting-details-tabs mb-6 flex gap-1 overflow-x-auto rounded-xl border border-slate-200 bg-white p-1.5 shadow-sm">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`shrink-0 rounded-lg px-4 py-2.5 text-sm font-medium transition ${
                activeTab === tab.id
                  ? "bg-blue-600 text-white"
                  : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
        {/* Overview */}
        {activeTab === "overview" && (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.7fr)_minmax(280px,1fr)]">
            <div className="space-y-6">
              <Panel
                title="Meeting summary"
                description="The summary saved for this meeting."
              >
                {analysis?.summary ? (
                  <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
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
                  <div className="flex flex-wrap gap-2">
                    {keyTopics.map((topic, index) => (
                      <span
                        key={`${topic}-${index}`}
                        className="rounded-full border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700"
                      >
                        {topic}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm leading-6 text-slate-500">
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
                  <div className="space-y-3">
                    {decisions.slice(0, 5).map((decision) => (
                      <article
                        key={decision.id}
                        className="rounded-xl border border-slate-200 p-4"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <h3 className="font-medium text-slate-900">
                            {decision.title}
                          </h3>
                          <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                            {titleCase(decision.status)}
                          </span>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-slate-600">
                          {decision.description}
                        </p>
                        <p className="mt-3 text-xs text-slate-500">
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
            <div className="space-y-6">
              <Panel
                title="Meeting information"
                description="Details about the recording."
              >
                <dl className="space-y-4">
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
                      className="flex items-start justify-between gap-4 border-b border-slate-100 pb-3 last:border-0 last:pb-0"
                    >
                      <dt className="text-sm text-slate-500">{label}</dt>
                      <dd className="text-right text-sm font-medium text-slate-800">
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
                  <div className="space-y-4">
                    {commitments.slice(0, 5).map((item) => (
                      <div
                        key={item.id}
                        className="border-b border-slate-100 pb-4 last:border-0 last:pb-0"
                      >
                        <p className="text-sm font-medium leading-6 text-slate-800">
                          {item.task}
                        </p>
                        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
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
                        className="text-sm font-medium text-blue-700 hover:text-blue-900"
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
              className="mb-5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
            {filteredTranscript.length > 0 ? (
              <div className="space-y-3">
                {filteredTranscript.map((segment) => (
                  <article
                    key={segment.id}
                    className="group rounded-2xl border border-slate-200 bg-white p-5 transition hover:border-blue-200 hover:shadow-sm"
                  >
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                      <span className="text-sm font-semibold text-slate-800">
                        {segment.speaker_name ||
                          segment.speaker_label ||
                          "Unknown speaker"}
                      </span>
                      <span className="font-mono text-xs text-slate-500">
                        {formatTime(segment.start_time)} –{" "}
                        {formatTime(segment.end_time)}
                      </span>
                    </div>
                    <p className="whitespace-pre-wrap border-l-2 border-blue-100 pl-4 text-sm leading-7 text-slate-700">
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
          <div className="space-y-6">
            <Panel
              title="Decisions"
              description={`${decisions.length} saved decisions`}
            >
              {decisions.length > 0 ? (
                <div className="space-y-3">
                  {decisions.map((decision) => (
                    <article
                      key={decision.id}
                      className="rounded-xl border border-slate-200 p-4 sm:p-5"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h3 className="font-semibold text-slate-900">
                            {decision.title}
                          </h3>
                          <p className="mt-2 text-sm leading-6 text-slate-600">
                            {decision.description}
                          </p>
                        </div>
                        <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                          {titleCase(decision.status)}
                        </span>
                      </div>
                      <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
                        <span>
                          Confidence: {confidencePercent(decision.confidence)}
                        </span>
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
                className="mb-5 w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
              {filteredCommitments.length > 0 ? (
                <div className="space-y-3">
                  {filteredCommitments.map((item) => (
                    <article
                      key={item.id}
                      className="rounded-xl border border-slate-200 p-4 sm:p-5"
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <h3 className="font-medium leading-6 text-slate-900">
                            {item.task}
                          </h3>
                          {item.notes && (
                            <p className="mt-2 text-sm leading-6 text-slate-500">
                              {item.notes}
                            </p>
                          )}
                        </div>
                        <span className="shrink-0 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
                          {titleCase(item.status)}
                        </span>
                      </div>
                      <div className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
                        <div>
                          <p className="text-xs text-slate-500">Deadline</p>
                          <p className="mt-1 font-medium text-slate-800">
                            {item.deadline_text ||
                              (item.deadline
                                ? formatDate(item.deadline)
                                : "Not specified")}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500">Strength</p>
                          <p className="mt-1 font-medium text-slate-800">
                            {titleCase(item.strength)}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-slate-500">Confidence</p>
                          <p className="mt-1 font-medium text-slate-800">
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
              <div className="space-y-3">
                {evidence.map((item) => (
                  <article
                    key={item.id}
                    className="rounded-xl border border-slate-200 p-4 sm:p-5"
                  >
                    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                      <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
                        {titleCase(item.evidence_type)}
                      </span>
                      <span className="text-xs text-slate-500">
                        Confidence: {confidencePercent(item.confidence)}
                      </span>
                    </div>
                    <blockquote className="border-l-2 border-slate-300 pl-4 text-sm leading-7 text-slate-700">
                      {item.snippet}
                    </blockquote>
                    <div className="mt-4 flex flex-wrap gap-4 text-xs text-slate-500">
                      {item.transcript_segment_id && (
                        <span>
                          Transcript segment linked
                        </span>
                      )}
                      {item.decision_id && (
                        <span>Decision linked</span>
                      )}
                      {item.commitment_id && (
                        <span>Commitment linked</span>
                      )}
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
        <footer className="mt-8 flex flex-col gap-2 border-t border-slate-200 pt-5 text-xs text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <p>Meeting Intelligence & Accountability System</p>
          <p>
            {analysis
              ? "Displaying the analysis returned by the backend."
              : "No saved analysis loaded."}
          </p>
        </footer>
      </div>
    </main>
  );
}
