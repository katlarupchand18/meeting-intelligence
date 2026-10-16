"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

const API =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Meeting = {
  id: string;
  title?: string | null;
  description?: string | null;
  meeting_type?: string | null;
  status?: string | null;
  created_at?: string | null;
  duration?: number | null;
  duration_seconds?: number | null;
  filename?: string | null;
};

type Commitment = {
  id?: string;
  status?: string | null;
  owner?: string | null;
  owner_name?: string | null;
  due_date?: string | null;
};

type Summary = {
  summary?: string | null;
  meeting_summary?: string | null;
  topics?: string[] | null;
  key_topics?: string[] | null;
};

function extractArray<T>(data: any): T[] {
  if (Array.isArray(data)) return data;

  if (Array.isArray(data?.meetings)) return data.meetings;
  if (Array.isArray(data?.data)) return data.data;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.items)) return data.items;

  return [];
}

function formatDate(value?: string | null): string {
  if (!value) return "Date unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) return value;

  return date.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function formatDuration(seconds?: number | null): string {
  if (seconds == null || !Number.isFinite(seconds)) {
    return "Duration unavailable";
  }

  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);

  if (hours > 0) return `${hours}h ${minutes}m`;

  return `${minutes} min`;
}

function statusClass(status?: string | null): string {
  const value = (status || "").toLowerCase();

  if (
    value.includes("complete") ||
    value.includes("success") ||
    value === "done"
  ) {
    return "meeting-status status-completed";
  }

  if (
    value.includes("fail") ||
    value.includes("error")
  ) {
    return "meeting-status status-error";
  }

  return "meeting-status status-processing";
}

function normalizeStatus(status?: string | null): string {
  if (!status) return "Available";

  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function getMeetingId(meeting: Meeting): string {
  return String(meeting.id || "");
}

export default function DashboardPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [commitments, setCommitments] = useState<Commitment[]>([]);
  const [summaries, setSummaries] = useState<Record<string, Summary>>({});

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const loadDashboard = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    setError("");

    try {
      const [meetingsResponse, healthResponse] = await Promise.all([
        fetch(`${API}/api/meetings`, { cache: "no-store" }),
        fetch(`${API}/health`, { cache: "no-store" }).catch(() => null),
      ]);

      setBackendOnline(Boolean(healthResponse?.ok));

      if (!meetingsResponse.ok) {
        throw new Error(
          `Unable to load meetings (${meetingsResponse.status}).`
        );
      }

      const meetingsData = await meetingsResponse.json();
      const meetingList = extractArray<Meeting>(meetingsData);

      setMeetings(meetingList);

      // Fetch existing commitment and summary information.
      const results = await Promise.all(
        meetingList.map(async (meeting) => {
          const meetingId = getMeetingId(meeting);

          if (!meetingId) {
            return {
              id: "",
              commitments: [] as Commitment[],
              summary: null as Summary | null,
            };
          }

          const [commitmentResult, summaryResult] = await Promise.all([
            fetch(`${API}/api/commitments/meeting/${meetingId}`, {
              cache: "no-store",
            }).catch(() => null),

            fetch(`${API}/api/analysis/meetings/${meetingId}/summary`, {
              cache: "no-store",
            }).catch(() => null),
          ]);

          let meetingCommitments: Commitment[] = [];
          let meetingSummary: Summary | null = null;

          if (commitmentResult?.ok) {
            try {
              const data = await commitmentResult.json();

              meetingCommitments = extractArray<Commitment>(data);
            } catch {
              meetingCommitments = [];
            }
          }

          if (summaryResult?.ok) {
            try {
              meetingSummary = await summaryResult.json();
            } catch {
              meetingSummary = null;
            }
          }

          return {
            id: meetingId,
            commitments: meetingCommitments,
            summary: meetingSummary,
          };
        })
      );

      const allCommitments: Commitment[] = [];
      const summaryMap: Record<string, Summary> = {};

      for (const result of results) {
        allCommitments.push(...result.commitments);

        if (result.id && result.summary) {
          summaryMap[result.id] = result.summary;
        }
      }

      setCommitments(allCommitments);
      setSummaries(summaryMap);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while loading the dashboard."
      );
      setBackendOnline(false);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const filteredMeetings = useMemo(() => {
    const query = search.trim().toLowerCase();

    return meetings.filter((meeting) => {
      const matchesSearch =
        !query ||
        (meeting.title || "").toLowerCase().includes(query) ||
        (meeting.description || "").toLowerCase().includes(query) ||
        (meeting.meeting_type || "").toLowerCase().includes(query);

      const status = (meeting.status || "").toLowerCase();

      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "completed" &&
          (status.includes("complete") ||
            status.includes("success") ||
            status === "done")) ||
        (statusFilter === "processing" &&
          !status.includes("complete") &&
          !status.includes("success") &&
          status !== "done" &&
          !status.includes("fail") &&
          !status.includes("error")) ||
        (statusFilter === "failed" &&
          (status.includes("fail") || status.includes("error")));

      return matchesSearch && matchesStatus;
    });
  }, [meetings, search, statusFilter]);

  const completedMeetings = meetings.filter((meeting) => {
    const status = (meeting.status || "").toLowerCase();

    return (
      status.includes("complete") ||
      status.includes("success") ||
      status === "done"
    );
  }).length;

  const openCommitments = commitments.filter((commitment) => {
    const status = (commitment.status || "open").toLowerCase();

    return ![
      "completed",
      "complete",
      "done",
      "cancelled",
      "canceled",
    ].includes(status);
  }).length;

  const recentMeetings = [...filteredMeetings].sort((a, b) => {
    const dateA = a.created_at
      ? new Date(a.created_at).getTime()
      : 0;

    const dateB = b.created_at
      ? new Date(b.created_at).getTime()
      : 0;

    return dateB - dateA;
  });

  const latestSummaries = recentMeetings
    .filter((meeting) => {
      const summary = summaries[getMeetingId(meeting)];

      return Boolean(summary?.summary || summary?.meeting_summary);
    })
    .slice(0, 3);

  return (
    <div className="zoom-app">
      {/* Sidebar */}
      <aside className="zoom-sidebar">
        <Link href="/" className="zoom-brand">
          <span className="zoom-brand-icon">M</span>

          <span>
            <strong>Meeting Intelligence</strong>
            <small>AI-powered accountability</small>
          </span>
        </Link>

        <div className="sidebar-label">WORKSPACE</div>

        <nav className="sidebar-nav" aria-label="Main navigation">
          <Link href="/" className="nav-item active" aria-current="page">
            <span className="nav-icon">⌂</span>
            <span>Dashboard</span>
          </Link>

          <a
            href="#meetings"
            className="nav-item"
            onClick={(event) => {
              event.preventDefault();
              document.getElementById("meetings")?.scrollIntoView({
                behavior: "smooth",
              });
            }}
          >
            <span className="nav-icon">▤</span>
            <span>My meetings</span>
          </a>

          <Link href="/meetings/new" className="nav-item">
            <span className="nav-icon">＋</span>
            <span>New meeting</span>
          </Link>
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-help-icon">?</div>

          <div>
            <strong>Meeting workspace</strong>
            <p>Turn discussions into decisions and actions.</p>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="zoom-main">
        <header className="zoom-topbar">
          <div className="topbar-breadcrumb">
            <strong>Dashboard</strong>
          </div>

          <div className="topbar-status">
            <span className="status-dot" />
            {backendOnline === null
              ? "Connecting..."
              : backendOnline
                ? "Backend connected"
                : "Backend unavailable"}
          </div>
        </header>

        <div className="workspace-content">
          {/* Welcome section */}
          <section className="welcome-row">
            <div>
              <span className="eyebrow">YOUR WORKSPACE</span>

              <h1>Meeting dashboard</h1>

              <p>
                Review conversations, track commitments, and keep
                decisions moving forward.
              </p>
            </div>

            <div className="quick-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => void loadDashboard(true)}
                disabled={loading || refreshing}
              >
                {refreshing ? "Refreshing..." : "↻ Refresh"}
              </button>

              <Link href="/meetings/new" className="primary-button">
                ＋ New meeting
              </Link>
            </div>
          </section>

          {/* Errors */}
          {error && (
            <div className="meeting-alert meeting-alert-error" role="alert">
              <strong>Unable to load dashboard.</strong>
              <p>{error}</p>

              <button
                type="button"
                className="secondary-button"
                onClick={() => void loadDashboard(true)}
              >
                Try again
              </button>
            </div>
          )}

          {/* Metrics */}
          <section className="metrics-grid" aria-label="Meeting statistics">
            <article className="metric-card">
              <h3>Total meetings</h3>
              <strong>
                {loading ? "—" : meetings.length}
              </strong>
              <p>Recordings in your workspace</p>
            </article>

            <article className="metric-card">
              <h3>Completed meetings</h3>
              <strong>
                {loading ? "—" : completedMeetings}
              </strong>
              <p>Meetings marked completed</p>
            </article>

            <article className="metric-card">
              <h3>Commitments</h3>
              <strong>
                {loading ? "—" : commitments.length}
              </strong>
              <p>Extracted commitment records</p>
            </article>

            <article className="metric-card">
              <h3>Open action items</h3>
              <strong>
                {loading ? "—" : openCommitments}
              </strong>
              <p>Items not marked completed</p>
            </article>
          </section>

          {/* Recent meetings */}
          <section className="meeting-section" id="meetings">
            <div className="meeting-section-header">
              <div>
                <h2>Recent meetings</h2>
                <p>
                  {loading
                    ? "Loading your meetings..."
                    : `${filteredMeetings.length} meeting${
                        filteredMeetings.length === 1 ? "" : "s"
                      } found`}
                </p>
              </div>

              <Link href="/meetings/new" className="secondary-button">
                ＋ Add recording
              </Link>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row">
              <input
                type="search"
                className="meeting-search"
                placeholder="Search meetings by title or description..."
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                aria-label="Search meetings"
              />

              <select
                className="meeting-search"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value)}
                aria-label="Filter meetings by status"
              >
                <option value="all">All statuses</option>
                <option value="completed">Completed</option>
                <option value="processing">In progress / available</option>
                <option value="failed">Failed</option>
              </select>
            </div>

            {loading ? (
              <div className="empty-state" aria-live="polite">
                <div className="loading-spinner" />
                <h3>Loading meetings</h3>
                <p>
                  Retrieving your meeting records and available insights.
                </p>
              </div>
            ) : recentMeetings.length > 0 ? (
              <div className="meeting-list">
                {recentMeetings.map((meeting) => {
                  const meetingId = getMeetingId(meeting);
                  const summary = summaries[meetingId];

                  return (
                    <article
                      className="meeting-row"
                      key={meetingId || meeting.title}
                    >
                      <div>
                        <h3>
                          <Link
                            href={`/meetings/${meetingId}`}
                            className="hover:text-blue-600"
                          >
                            {meeting.title || "Untitled meeting"}
                          </Link>
                        </h3>

                        <p>
                          {meeting.description ||
                            "No description provided."}
                        </p>

                        <p>
                          {formatDate(meeting.created_at)}
                          {" · "}
                          {meeting.meeting_type || "Meeting"}
                          {" · "}
                          {formatDuration(
                            meeting.duration_seconds ??
                              meeting.duration
                          )}
                        </p>

                        {summary && (
                          <p className="mt-2">
                            {summary.summary ||
                              summary.meeting_summary}
                          </p>
                        )}
                      </div>

                      <div className="flex shrink-0 flex-col items-start gap-3 sm:items-end">
                        <span className={statusClass(meeting.status)}>
                          {normalizeStatus(meeting.status)}
                        </span>

                        <Link
                          href={`/meetings/${meetingId}`}
                          className="text-button"
                        >
                          Open meeting →
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">▤</div>

                <h3>
                  {meetings.length
                    ? "No matching meetings"
                    : "Your workspace is ready"}
                </h3>

                <p>
                  {meetings.length
                    ? "Try another search term or choose a different status filter."
                    : "Upload an audio or video recording to create your first meeting and start extracting useful insights."}
                </p>

                {meetings.length === 0 && (
                  <Link
                    href="/meetings/new"
                    className="primary-button"
                  >
                    ＋ Upload a meeting
                  </Link>
                )}
              </div>
            )}
          </section>

          {/* Available AI summaries */}
          <section className="meeting-section">
            <div className="meeting-section-header">
              <div>
                <h2>Meeting insights</h2>
                <p>
                  Summaries returned by your existing analysis service
                </p>
              </div>
            </div>

            {loading ? (
              <div className="empty-state">
                <p>Loading available insights...</p>
              </div>
            ) : latestSummaries.length > 0 ? (
              <div className="insight-grid">
                {latestSummaries.map((meeting) => {
                  const meetingId = getMeetingId(meeting);
                  const summary = summaries[meetingId];

                  const topics =
                    summary?.topics || summary?.key_topics || [];

                  return (
                    <article
                      className="insight-card"
                      key={meetingId}
                    >
                      <span className="eyebrow">MEETING SUMMARY</span>

                      <h3>{meeting.title || "Untitled meeting"}</h3>

                      <p>
                        {summary?.summary ||
                          summary?.meeting_summary}
                      </p>

                      {topics.length > 0 && (
                        <div className="mt-4 flex flex-wrap gap-2">
                          {topics.slice(0, 4).map((topic, index) => (
                            <span
                              key={`${topic}-${index}`}
                              className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs text-blue-700"
                            >
                              {topic}
                            </span>
                          ))}
                        </div>
                      )}

                      <Link
                        href={`/meetings/${meetingId}`}
                        className="text-button"
                      >
                        Review meeting →
                      </Link>
                    </article>
                  );
                })}
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">✦</div>

                <h3>No meeting insights yet</h3>

                <p>
                  When your analysis service returns meeting summaries,
                  they will appear here. Open a meeting to review its
                  available analysis.
                </p>
              </div>
            )}
          </section>

          <footer className="mt-10 border-t border-slate-200 pt-5 text-xs text-slate-400">
            Meeting Intelligence · Your conversations, organized.
          </footer>
        </div>
      </main>
    </div>
  );
}