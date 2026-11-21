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
        `Subject: ${subject}\\n\\n${body}`
      );
      setCopied(true);
    } catch {
      setError("Unable to copy. Please copy the email manually.");
    }
  }

  return (
    <main className="mx-auto max-w-5xl space-y-8 px-6 py-10">
      <div>
        <Link
          href="/"
          className="text-sm text-blue-600 hover:underline"
        >
          ← Dashboard
        </Link>

        <h1 className="mt-4 text-3xl font-bold">
          AI Meeting Follow-up Generator
        </h1>

        <p className="mt-2 text-gray-600">
          Generate an editable follow-up email from meeting
          decisions, commitments, owners, and deadlines.
        </p>
      </div>

      <section className="space-y-4 rounded-xl border p-6">
        <label
          htmlFor="meeting"
          className="block font-semibold"
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
          className="w-full rounded-lg border p-3 text-gray-900"
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
          className="rounded-lg bg-blue-600 px-5 py-3 font-medium text-white disabled:opacity-50"
        >
          {generating
            ? "Generating email..."
            : "Generate Follow-up Email"}
        </button>

        {generating && (
          <p className="text-sm text-gray-500">
            Ollama is generating your draft. This may take
            a few minutes.
          </p>
        )}

        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
      </section>

      {result && (
        <section className="space-y-5 rounded-xl border p-6">
          <div>
            <h2 className="text-xl font-bold">
              Generated Email
            </h2>

            <p className="mt-1 text-sm text-amber-700">
              AI-generated draft — review facts, dates,
              owners, and verification statuses before sending.
            </p>
          </div>

          <div className="flex flex-wrap gap-3 text-sm">
            <span className="rounded bg-gray-100 px-3 py-2 text-gray-900">
              Action items: {result.action_item_count}
            </span>
            <span className="rounded bg-gray-100 px-3 py-2 text-gray-900">
              Overdue: {result.overdue_count}
            </span>
            <span className="rounded bg-gray-100 px-3 py-2 text-gray-900">
              Decisions: {result.decision_count}
            </span>
          </div>

          <div>
            <label
              htmlFor="subject"
              className="mb-2 block font-semibold"
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
              className="w-full rounded-lg border p-3 text-gray-900"
            />
          </div>

          <div>
            <label
              htmlFor="body"
              className="mb-2 block font-semibold"
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
              className="w-full rounded-lg border p-3 font-mono text-sm text-gray-900"
            />
          </div>

          <button
            onClick={copyEmail}
            disabled={!subject.trim() || !body.trim()}
            className="rounded-lg bg-green-600 px-5 py-3 font-medium text-white disabled:opacity-50"
          >
            {copied ? "Copied!" : "Copy Email"}
          </button>
        </section>
      )}
    </main>
  );
}
