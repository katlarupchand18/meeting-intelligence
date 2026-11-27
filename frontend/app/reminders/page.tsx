"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

const API =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

type Reminder = {
  commitment_id: string;
  meeting_id: string;
  meeting_title: string | null;
  owner_name: string | null;
  task: string;
  status: string;
  deadline: string | null;
  deadline_text: string | null;
  verification_status: string | null;
};

type MeetingGroup = {
  meeting_id: string;
  meeting_title: string;
  counts: {
    overdue: number;
    upcoming: number;
    needs_deadline_review: number;
    no_deadline: number;
  };
  overdue: Reminder[];
  upcoming: Reminder[];
  needs_deadline_review: Reminder[];
  no_deadline: Reminder[];
};

type Preview = {
  today: string;
  days_ahead: number;
  meetings: MeetingGroup[];
};

const sections = [
  {
    key: "overdue",
    title: "Overdue Commitments",
    description: "Confirmed deadlines that have passed.",
  },
  {
    key: "upcoming",
    title: "Upcoming Commitments",
    description: "Confirmed deadlines within the selected window.",
  },
  {
    key: "needs_deadline_review",
    title: "Deadlines Requiring Review",
    description: "Text-based deadlines needing confirmation.",
  },
  {
    key: "no_deadline",
    title: "Commitments Without Deadlines",
    description: "Active tasks with no recorded deadline.",
  },
] as const;

export default function RemindersPage() {
  const [daysAhead, setDaysAhead] = useState(7);
  const [meetingId, setMeetingId] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [meetings, setMeetings] = useState<Array<{id: string, title: string}>>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dates, setDates] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

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

  const loadPreview = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      let url = `${API}/api/reminders/by-meeting?days_ahead=${daysAhead}`;
      if (meetingId) {
        url += `&meeting_id=${meetingId}`;
      }
      const response = await fetch(url, { cache: "no-store" });

      if (!response.ok) {
        throw new Error("Unable to load reminder preview.");
      }

      const data: Preview = await response.json();
      setPreview(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unknown error"
      );
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, [daysAhead]);

  useEffect(() => {
    void loadPreview();
  }, [loadPreview, meetingId]);

  async function confirmDeadline(item: Reminder) {
    const selectedDate = dates[item.commitment_id];

    if (!selectedDate) {
      setMessage("Select a date before confirming.");
      return;
    }

    setSavingId(item.commitment_id);
    setMessage("");

    try {
      const response = await fetch(
        `${API}/api/commitments/${item.commitment_id}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ deadline: selectedDate }),
        }
      );

      if (!response.ok) {
        let detail = `HTTP ${response.status}`;

        try {
          const payload = await response.json();
          if (typeof payload.detail === "string") {
            detail = payload.detail;
          }
        } catch {
          // Keep the HTTP error message.
        }

        throw new Error(detail);
      }

      setMessage("Deadline confirmed successfully.");
      setDates((current) => {
        const updated = { ...current };
        delete updated[item.commitment_id];
        return updated;
      });

      await loadPreview();
    } catch (err) {
      setMessage(
        err instanceof Error ? err.message : "Unable to save deadline."
      );
    } finally {
      setSavingId(null);
    }
  }

  return (
    <main className="page-wrapper">
      <Link href="/" className="back-link">
        ← Dashboard
      </Link>

      <h1>Commitment Reminders</h1>

      <p className="text-slate-500">
        Review upcoming deadlines, overdue tasks, and
        commitments requiring deadline clarification.
      </p>

      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">INFO</span>
            <h2>Reminder Preview Only</h2>
          </div>
        </div>
        <p className="text-sm text-slate-500" style={{ marginTop: 8 }}>
          No emails or notifications are sent. Text-based deadlines require confirmation.
        </p>
      </section>

      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">FILTERS</span>
            <h2>Reminder Settings</h2>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", marginTop: 16 }}>
          <label htmlFor="days" style={{ fontWeight: 500 }}>
            Upcoming deadline window
          </label>

          <select
            id="days"
            value={daysAhead}
            onChange={(event) =>
              setDaysAhead(Number(event.target.value))
            }
            className="meeting-search"
            style={{ minWidth: 180 }}
          >
            <option value={3}>Next 3 days</option>
            <option value={7}>Next 7 days</option>
            <option value={14}>Next 14 days</option>
            <option value={30}>Next 30 days</option>
          </select>

          <button
            type="button"
            onClick={() => void loadPreview()}
            className="primary-button"
          >
            Refresh
          </button>
        </div>
      </section>

      {message && (
        <p role="status" className="meeting-alert meeting-alert-success" style={{ marginTop: 16 }}>
          {message}
        </p>
      )}

      {error && (
        <p role="alert" className="meeting-alert meeting-alert-error" style={{ marginTop: 16 }}>
          {error}
        </p>
      )}

      {loading && (
        <p className="text-slate-500 mt-8">Loading reminders...</p>
      )}

      {preview && !loading && (
        <>
          <section className="meeting-card" style={{ marginTop: 24 }}>
            <div className="meeting-card-heading">
              <div>
                <span className="eyebrow">FILTER</span>
                <h2>Filter by Meeting</h2>
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <label htmlFor="meeting-filter" style={{ fontWeight: 500, display: "block", marginBottom: 8 }}>
                Filter by meeting
              </label>
              <select
                id="meeting-filter"
                value={meetingId}
                onChange={(event) => setMeetingId(event.target.value)}
                className="meeting-search"
                style={{ minWidth: 300 }}
              >
                <option value="">All meetings</option>
                {meetings.map((meeting) => (
                  <option key={meeting.id} value={meeting.id}>
                    {meeting.title}
                  </option>
                ))}
              </select>
            </div>
          </section>

          {preview.meetings.length === 0 && (
            <p className="text-slate-500 text-center mt-8 py-12">
              No active commitments found for the selected period.
            </p>
          )}

          {preview.meetings.map((meetingGroup) => (
            <section key={meetingGroup.meeting_id} className="meeting-card" style={{ marginTop: 24 }}>
              <div className="meeting-card-heading">
                <div>
                  <span className="eyebrow">MEETING</span>
                  <h2>{meetingGroup.meeting_title}</h2>
                </div>
                <Link
                  href={`/meetings/${meetingGroup.meeting_id}`}
                  className="primary-button"
                  style={{ fontSize: 14, padding: "8px 16px" }}
                >
                  View Meeting →
                </Link>
              </div>
              <p className="text-sm text-slate-500" style={{ marginTop: 8 }}>
                {meetingGroup.counts.overdue} overdue, {meetingGroup.counts.upcoming} upcoming, {meetingGroup.counts.needs_deadline_review} need review, {meetingGroup.counts.no_deadline} no deadline
              </p>

              {sections.map((section) => {
                const items = meetingGroup[section.key as keyof MeetingGroup];
                if (!Array.isArray(items) || items.length === 0) return null;
                return (
                  <div key={section.key} style={{ marginTop: 20 }}>
                    <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
                      {section.title} ({items.length})
                    </h3>
                    {items.map((item) => (
                      <article
                        key={item.commitment_id}
                        style={{
                          border: "1px solid #e2e8f0",
                          padding: 20,
                          borderRadius: 8,
                          marginTop: 12,
                          background: "#fff",
                        }}
                      >
                        <p style={{ fontWeight: 600 }}>{item.task}</p>

                        <p style={{ marginTop: 8, fontSize: 14, color: "#64748b" }}>
                          Owner: {item.owner_name || "Unassigned"}
                        </p>

                        <p style={{ marginTop: 4, fontSize: 14, color: "#64748b" }}>
                          Deadline:{" "}
                          {item.deadline ||
                            item.deadline_text ||
                            "Not specified"}
                        </p>

                        <p style={{ marginTop: 8, fontSize: 12, color: "#94a3b8" }}>
                          Status: {item.status} · Verification:{" "}
                          {item.verification_status || "Unknown"}
                        </p>

                        {item.verification_status !== "approved" &&
                          item.verification_status !== "rejected" && (
                            <div style={{ marginTop: 16, display: "flex", flexWrap: "wrap", gap: 12, alignItems: "center" }}>
                              <label
                                htmlFor={`deadline-${item.commitment_id}`}
                                style={{ fontSize: 14, fontWeight: 500 }}
                              >
                                Confirm deadline
                              </label>

                              <input
                                id={`deadline-${item.commitment_id}`}
                                type="date"
                                value={
                                  dates[item.commitment_id] ||
                                  item.deadline ||
                                  ""
                                }
                                onChange={(event) =>
                                  setDates((current) => ({
                                    ...current,
                                    [item.commitment_id]: event.target.value,
                                  }))
                                }
                                style={{
                                  padding: "8px 12px",
                                  border: "1px solid #cbd5e1",
                                  borderRadius: 8,
                                  color: "inherit",
                                  background: "transparent",
                                  fontSize: 14,
                                }}
                              />

                              <button
                                type="button"
                                disabled={
                                  savingId !== null ||
                                  !dates[item.commitment_id]
                                }
                                onClick={() => void confirmDeadline(item)}
                                className="primary-button"
                                style={{ padding: "8px 16px", fontSize: 14 }}
                              >
                                {savingId === item.commitment_id
                                  ? "Saving..."
                                  : "Confirm Deadline"}
                              </button>
                            </div>
                          )}
                      </article>
                    ))}
                  </div>
                )
              })}
            </section>
          ))}
        </>
      )}
    </main>
  );
}