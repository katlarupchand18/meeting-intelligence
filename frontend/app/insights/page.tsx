"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

const API =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

type Meeting = {
  id: string;
  title: string;
};

type Participant = {
  id: string;
  meeting_id: string;
  name: string;
  role: string | null;
  speaker_label: string | null;
};

type Task = {
  id: string;
  task: string;
  status: string;
  deadline: string | null;
  deadline_text: string | null;
  overdue: boolean;
  verification_status: string;
};

type Decision = {
  id: string;
  title: string;
  description: string;
  status: string;
  verification_status: string;
};

type Insights = {
  participant: {
    id: string;
    name: string;
    role: string | null;
    organization: string | null;
    speaker_label: string | null;
  };
  meeting: {
    id: string;
    title: string;
    summary: string | null;
    created_at: string | null;
  };
  statistics: {
    total_tasks: number;
    pending_tasks: number;
    completed_tasks: number;
    overdue_tasks: number;
    meeting_decisions: number;
  };
  tasks: Task[];
  meeting_decisions: Decision[];
  requires_review: boolean;
};

export default function InsightsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [meetingId, setMeetingId] = useState("");
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [participantId, setParticipantId] = useState("");
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [error, setError] = useState("");

  const loadMeetings = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API}/api/meetings`);

      if (!response.ok) {
        throw new Error("Failed to load meetings.");
      }

      const data = await response.json();

      const items: Meeting[] = Array.isArray(data)
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
        err instanceof Error ? err.message : "Failed to load meetings."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMeetings();
  }, [loadMeetings]);

  useEffect(() => {
    if (!meetingId) {
      setParticipants([]);
      setParticipantId("");
      setInsights(null);
      return;
    }

    let active = true;

    async function loadParticipants() {
      setError("");
      setParticipants([]);
      setParticipantId("");
      setInsights(null);

      try {
        const response = await fetch(
          `${API}/api/participants/meeting/${meetingId}`
        );

        if (!response.ok) {
          throw new Error("Failed to load participants.");
        }

        const data = await response.json();

        const items: Participant[] = Array.isArray(data)
          ? data
          : Array.isArray(data.participants)
          ? data.participants
          : [];

        if (!active) return;

        setParticipants(items);

        if (items.length > 0) {
          setParticipantId(items[0].id);
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load participants."
          );
        }
      }
    }

    void loadParticipants();

    return () => {
      active = false;
    };
  }, [meetingId]);

  useEffect(() => {
    if (!participantId) {
      setInsights(null);
      return;
    }

    let active = true;

    async function loadInsights() {
      setLoadingInsights(true);
      setError("");
      setInsights(null);

      try {
        const response = await fetch(
          `${API}/api/insights/participants/${participantId}`
        );

        if (!response.ok) {
          throw new Error("Failed to load participant insights.");
        }

        const data: Insights = await response.json();

        if (active) {
          setInsights(data);
        }
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load insights."
          );
        }
      } finally {
        if (active) {
          setLoadingInsights(false);
        }
      }
    }

    void loadInsights();

    return () => {
      active = false;
    };
  }, [participantId]);

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
      <header>
        <Link
          href="/"
          className="text-sm text-blue-600 hover:underline"
        >
          ← Dashboard
        </Link>

        <h1 className="mt-4 text-3xl font-bold">
          Role-Specific Insights
        </h1>

        <p className="mt-2 text-gray-600">
          View a participant's responsibilities, deadlines,
          meeting context, and relevant decisions.
        </p>
      </header>

      <section className="grid gap-5 rounded-xl border p-6 md:grid-cols-2">
        <div>
          <label
            htmlFor="meeting"
            className="mb-2 block font-semibold"
          >
            Meeting
          </label>

          <select
            id="meeting"
            value={meetingId}
            onChange={(event) => setMeetingId(event.target.value)}
            disabled={loading}
            className="w-full rounded-lg border p-3 text-gray-900"
          >
            {meetings.length === 0 && (
              <option value="">
                {loading ? "Loading..." : "No meetings found"}
              </option>
            )}

            {meetings.map((meeting) => (
              <option key={meeting.id} value={meeting.id}>
                {meeting.title}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label
            htmlFor="participant"
            className="mb-2 block font-semibold"
          >
            Participant
          </label>

          <select
            id="participant"
            value={participantId}
            onChange={(event) => setParticipantId(event.target.value)}
            disabled={!participants.length}
            className="w-full rounded-lg border p-3 text-gray-900"
          >
            {participants.length === 0 && (
              <option value="">No participants available</option>
            )}

            {participants.map((participant) => (
              <option key={participant.id} value={participant.id}>
                {participant.name}
                {participant.role ? ` — ${participant.role}` : ""}
              </option>
            ))}
          </select>
        </div>
      </section>

      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}

      {loadingInsights && (
        <p className="text-gray-500">
          Loading participant insights...
        </p>
      )}

      {insights && (
        <>
          <section className="rounded-xl border p-6">
            <h2 className="text-2xl font-bold">
              {insights.participant.name}
            </h2>

            <p className="mt-2 text-gray-600">
              Role: {insights.participant.role || "Not specified"}
            </p>

            {insights.participant.organization && (
              <p className="text-gray-600">
                Organization: {insights.participant.organization}
              </p>
            )}

            <p className="mt-3 text-sm text-amber-700">
              Meeting-specific insights. AI-extracted records may
              require human verification.
            </p>
          </section>

          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
            {[
              ["Total Tasks", insights.statistics.total_tasks],
              ["Pending", insights.statistics.pending_tasks],
              ["Completed", insights.statistics.completed_tasks],
              ["Overdue", insights.statistics.overdue_tasks],
              ["Meeting Decisions", insights.statistics.meeting_decisions],
            ].map(([label, value]) => (
              <div
                key={label}
                className="rounded-xl border p-5"
              >
                <p className="text-sm text-gray-500">{label}</p>
                <p className="mt-2 text-3xl font-bold">{value}</p>
              </div>
            ))}
          </section>

          <section className="rounded-xl border p-6">
            <h2 className="text-xl font-bold">Meeting Summary</h2>
            <p className="mt-2 font-medium">
              {insights.meeting.title}
            </p>
            <p className="mt-3 whitespace-pre-wrap text-gray-600">
              {insights.meeting.summary ||
                "No meeting summary available."}
            </p>
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-bold">
              Assigned Action Items
            </h2>

            {insights.tasks.length === 0 && (
              <p className="text-gray-500">
                No assigned action items for this participant.
              </p>
            )}

            {insights.tasks.map((task) => (
              <article
                key={task.id}
                className="rounded-xl border p-5"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-gray-100 px-3 py-1 text-sm text-gray-900">
                    {task.status.replaceAll("_", " ")}
                  </span>

                  {task.overdue && (
                    <span className="rounded bg-red-100 px-3 py-1 text-sm text-red-700">
                      Overdue
                    </span>
                  )}

                  <span className="rounded bg-amber-100 px-3 py-1 text-sm text-amber-800">
                    Verification: {task.verification_status}
                  </span>
                </div>

                <p className="mt-3 font-medium">{task.task}</p>

                <p className="mt-2 text-sm text-gray-500">
                  Deadline:{" "}
                  {task.deadline ||
                    task.deadline_text ||
                    "Not specified"}
                </p>
              </article>
            ))}
          </section>

          <section className="space-y-4">
            <h2 className="text-xl font-bold">
              Meeting Decisions
            </h2>

            <p className="text-sm text-gray-500">
              These decisions belong to the selected meeting.
              They are not necessarily attributed to this participant.
            </p>

            {insights.meeting_decisions.length === 0 && (
              <p className="text-gray-500">
                No current meeting decisions available.
              </p>
            )}

            {insights.meeting_decisions.map((decision) => (
              <article
                key={decision.id}
                className="rounded-xl border p-5"
              >
                <h3 className="font-semibold">{decision.title}</h3>

                <p className="mt-2 whitespace-pre-wrap text-gray-600">
                  {decision.description}
                </p>

                <p className="mt-3 text-sm text-gray-500">
                  Status: {decision.status} · Verification:{" "}
                  {decision.verification_status}
                </p>
              </article>
            ))}
          </section>
        </>
      )}
    </main>
  );
}
