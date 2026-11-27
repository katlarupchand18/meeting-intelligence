"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

type Meeting = {
  id: string;
  title: string;
};

type FollowupResult = {
  meeting_id: string;
  meeting_title: string;
  subject: string;
  body: string;
  action_item_count: number;
  overdue_count: number;
  decision_count: number;
  requires_review: boolean;
};

export default function FollowupsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [meetingId, setMeetingId] = useState("");
  const [loadingMeetings, setLoadingMeetings] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<FollowupResult | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    async function loadMeetings() {
      try {
        const response = await fetch(`${API}/api/meetings`);

        if (!response.ok) {
          throw new Error("Failed to load meetings.");
        }

        const data = await response.json();

        const items = Array.isArray(data)
          ? data
          : Array.isArray(data.meetings)
          ? data.meetings
          : Array.isArray(data.items)
          ? data.items
          : [];

        setMeetings(items);

        if (items.length > 0) {
          setMeetingId(items[0].id);
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load meetings."
        );
      } finally {
        setLoadingMeetings(false);
      }
    }

    void loadMeetings();
  }, []);

  async function generateFollowup() {
    if (!meetingId || generating) return;

    setGenerating(true);
    setError("");
    setResult(null);
    setSubject("");
    setBody("");
    setCopied(false);

    try {
      const response = await fetch(
        `${API}/api/followups/meeting/${meetingId}`,
        { method: "POST" }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Failed to generate follow-up."
        );
      }

      const data: FollowupResult = await response.json();

      setResult(data);
      setSubject(data.subject);
      setBody(data.body);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Follow-up generation failed."
      );
    } finally {
      setGenerating(false);
    }
  }

  async function copyEmail() {
    try {
      await navigator.clipboard.writeText(
        `Subject: ${subject}\n\n${body}`
      );
      setCopied(true);
    } catch {
      setError("Unable to copy. Please copy the email manually.");
    }
  }

  return (
    <main className="page-wrapper">
      <Link href="/" className="back-link">
        ← Dashboard
      </Link>

      <h1>AI Meeting Follow-up Generator</h1>

      <p className="text-slate-500">
        Generate an editable follow-up email from meeting
        decisions, commitments, owners, and deadlines.
      </p>

      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">SELECT MEETING</span>
            <h2>Choose a Meeting</h2>
          </div>
        </div>
        <div style={{ marginTop: 16 }}>
          <label
            htmlFor="meeting"
            style={{ display: "block", fontWeight: 500, marginBottom: 8 }}
          >
            Select meeting
          </label>

          <select
            id="meeting"
            value={meetingId}
            onChange={(event) => {
              setMeetingId(event.target.value);
              setResult(null);
              setSubject("");
              setBody("");
              setCopied(false);
            }}
            disabled={loadingMeetings || generating}
            className="meeting-search"
            style={{ minWidth: 300 }}
          >
            {meetings.length === 0 && (
              <option value="">
                {loadingMeetings
                  ? "Loading meetings..."
                  : "No meetings available"}
              </option>
            )}

            {meetings.map((meeting) => (
              <option key={meeting.id} value={meeting.id}>
                {meeting.title}
              </option>
            ))}
          </select>

          <button
            onClick={generateFollowup}
            disabled={!meetingId || generating}
            className="primary-button"
            style={{ marginTop: 16 }}
          >
            {generating
              ? "Generating email..."
              : "Generate Follow-up Email"}
          </button>

          {generating && (
            <p className="text-slate-500 mt-4">
              AI is generating your draft. This may take
              a few minutes.
            </p>
          )}

          {error && (
            <p role="alert" className="meeting-alert meeting-alert-error" style={{ marginTop: 16 }}>
              {error}
            </p>
          )}
        </div>
      </section>

      {result && (
        <section className="meeting-card" style={{ marginTop: 24 }}>
          <div className="meeting-card-heading">
            <div>
              <span className="eyebrow">GENERATED EMAIL</span>
              <h2>Follow-up Draft</h2>
            </div>
          </div>

          <div style={{ marginTop: 16 }}>
            <p className="text-sm text-amber-700 mb-4">
              AI-generated draft — review facts, dates,
              owners, and verification statuses before sending.
            </p>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
              <span style={{ padding: "6px 12px", borderRadius: 6, background: "#f1f5f9", fontSize: 13 }}>
                Action items: {result.action_item_count}
              </span>
              <span style={{ padding: "6px 12px", borderRadius: 6, background: "#fef2f2", color: "#991b1b", fontSize: 13 }}>
                Overdue: {result.overdue_count}
              </span>
              <span style={{ padding: "6px 12px", borderRadius: 6, background: "#eff6ff", color: "#1d4ed8", fontSize: 13 }}>
                Decisions: {result.decision_count}
              </span>
            </div>

            <div style={{ marginBottom: 20 }}>
              <label
                htmlFor="subject"
                style={{ display: "block", fontWeight: 500, marginBottom: 8 }}
              >
                Email subject
              </label>
              <input
                id="subject"
                value={subject}
                onChange={(event) => {
                  setSubject(event.target.value);
                  setCopied(false);
                }}
                className="meeting-search"
                style={{ fontSize: 16 }}
              />
            </div>

            <div style={{ marginBottom: 20 }}>
              <label
                htmlFor="body"
                style={{ display: "block", fontWeight: 500, marginBottom: 8 }}
              >
                Email body
              </label>
              <textarea
                id="body"
                value={body}
                onChange={(event) => {
                  setBody(event.target.value);
                  setCopied(false);
                }}
                rows={18}
                className="meeting-search"
                style={{ fontFamily: "monospace", fontSize: 14, minHeight: 300 }}
              />
            </div>

            <button
              onClick={copyEmail}
              disabled={!subject.trim() || !body.trim()}
              className="primary-button"
              style={{ background: "#10b981" }}
            >
              {copied ? "Copied!" : "Copy Email"}
            </button>
          </div>
        </section>
      )}
    </main>
  );
}