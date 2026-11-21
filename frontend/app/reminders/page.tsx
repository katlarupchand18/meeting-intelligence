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

type Preview = {
  today: string;
  days_ahead: number;
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
  delivery_enabled: boolean;
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
  const [preview, setPreview] = useState<Preview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dates, setDates] = useState<Record<string, string>>({});
  const [savingId, setSavingId] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  const loadPreview = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API}/api/reminders/preview?days_ahead=${daysAhead}`,
        { cache: "no-store" }
      );

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
  }, [loadPreview]);

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
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
      <header>
        <Link href="/" className="text-sm text-blue-600 hover:underline">
          ← Dashboard
        </Link>

        <h1 className="mt-4 text-3xl font-bold">
          Commitment Reminders
        </h1>

        <p className="mt-2 text-gray-600">
          Review upcoming deadlines, overdue tasks, and
          commitments requiring deadline clarification.
        </p>
      </header>

      <section className="rounded-xl border p-5">
        <p className="font-medium">Reminder preview only</p>
        <p className="mt-2 text-sm text-gray-600">
          No emails or notifications are sent.
          Text-based deadlines require confirmation.
        </p>
      </section>

      <section className="flex flex-wrap items-center gap-4">
        <label htmlFor="days" className="font-medium">
          Upcoming deadline window
        </label>

        <select
          id="days"
          value={daysAhead}
          onChange={(event) =>
            setDaysAhead(Number(event.target.value))
          }
          className="rounded-lg border p-3 text-gray-900"
        >
          <option value={3}>Next 3 days</option>
          <option value={7}>Next 7 days</option>
          <option value={14}>Next 14 days</option>
          <option value={30}>Next 30 days</option>
        </select>

        <button
          type="button"
          onClick={() => void loadPreview()}
          className="rounded-lg bg-indigo-600 px-4 py-3 font-medium text-white"
        >
          Refresh
        </button>
      </section>

      {message && (
        <p role="status" className="rounded-lg border p-3">
          {message}
        </p>
      )}

      {loading && <p>Loading reminders...</p>}

      {error && (
        <p role="alert" className="text-red-600">
          {error}
        </p>
      )}

      {preview && !loading && (
        <>
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {sections.map((section) => (
              <div
                key={section.key}
                className="rounded-xl border p-5"
              >
                <p className="text-sm text-gray-500">
                  {section.title}
                </p>
                <p className="mt-2 text-3xl font-bold">
                  {preview.counts[section.key]}
                </p>
              </div>
            ))}
          </section>

          {sections.map((section) => (
            <section key={section.key} className="space-y-4">
              <div>
                <h2 className="text-xl font-bold">
                  {section.title}
                </h2>
                <p className="mt-1 text-sm text-gray-500">
                  {section.description}
                </p>
              </div>

              {preview[section.key].length === 0 && (
                <p className="rounded-xl border p-5 text-gray-500">
                  No commitments in this category.
                </p>
              )}

              {preview[section.key].map((item) => (
                <article
                  key={item.commitment_id}
                  className="rounded-xl border p-5"
                >
                  <p className="font-semibold">{item.task}</p>

                  <p className="mt-2 text-sm text-gray-600">
                    Meeting: {item.meeting_title || "Unknown"}
                  </p>

                  <p className="text-sm text-gray-600">
                    Owner: {item.owner_name || "Unassigned"}
                  </p>

                  <p className="text-sm text-gray-600">
                    Deadline:{" "}
                    {item.deadline ||
                      item.deadline_text ||
                      "Not specified"}
                  </p>

                  <p className="mt-2 text-xs text-gray-500">
                    Status: {item.status} · Verification:{" "}
                    {item.verification_status || "Unknown"}
                  </p>

                  {item.verification_status !== "approved" &&
                    item.verification_status !== "rejected" && (
                      <div className="mt-4 flex flex-wrap items-center gap-3">
                        <label
                          htmlFor={`deadline-${item.commitment_id}`}
                          className="text-sm font-medium"
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
                          className="rounded-lg border p-2 text-gray-900"
                        />

                        <button
                          type="button"
                          disabled={
                            savingId !== null ||
                            !dates[item.commitment_id]
                          }
                          onClick={() => void confirmDeadline(item)}
                          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                        >
                          {savingId === item.commitment_id
                            ? "Saving..."
                            : "Confirm Deadline"}
                        </button>
                      </div>
                    )}
                </article>
              ))}
            </section>
          ))}
        </>
      )}
    </main>
  );
}
