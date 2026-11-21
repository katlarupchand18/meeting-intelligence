"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

const API =
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

type Reminder = {
  commitment_id: string;
  task: string;
  meeting_title: string | null;
  owner_name: string | null;
  deadline: string | null;
};

type ReminderPreview = {
  overdue: Reminder[];
  upcoming: Reminder[];
  counts: {
    overdue: number;
    upcoming: number;
  };
};

export default function ReminderBell() {
  const [data, setData] = useState<ReminderPreview | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const response = await fetch(
        `${API}/api/reminders/preview?days_ahead=7`,
        { cache: "no-store" }
      );

      if (!response.ok) {
        throw new Error(`Reminder API returned ${response.status}`);
      }

      const preview: ReminderPreview = await response.json();
      setData(preview);
      setError("");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load reminders"
      );
    }
  }, []);

  useEffect(() => {
    void load();

    const timer = window.setInterval(() => {
      if (document.visibilityState === "visible") {
        void load();
      }
    }, 60000);

    const refreshOnFocus = () => {
      void load();
    };

    window.addEventListener("focus", refreshOnFocus);

    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refreshOnFocus);
    };
  }, [load]);

  const overdue = data?.overdue || [];
  const upcoming = data?.upcoming || [];
  const count = overdue.length + upcoming.length;

  return (
    <div className="relative inline-block">
      <button
        type="button"
        aria-label={`Commitment reminders: ${count} alerts`}
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
        className="relative rounded-xl border px-4 py-3 text-sm font-medium hover:bg-gray-100"
      >
        <span aria-hidden="true">🔔</span>
        <span className="ml-2">Reminders</span>

        {count > 0 && (
          <span className="ml-2 rounded-full bg-red-600 px-2 py-0.5 text-xs text-white">
            {count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-[min(90vw,380px)] rounded-xl border bg-white p-4 text-gray-900 shadow-xl">
          <h3 className="font-semibold">Commitment alerts</h3>

          <p className="mt-1 text-xs text-gray-500">
            Checks automatically every 60 seconds while the dashboard is open.
          </p>

          {error && (
            <p role="alert" className="mt-3 text-sm text-red-600">
              {error}
            </p>
          )}

          {!error && count === 0 && (
            <p className="mt-3 text-sm text-gray-600">
              No overdue or upcoming confirmed deadlines.
            </p>
          )}

          <div className="mt-3 max-h-72 space-y-3 overflow-y-auto">
            {overdue.map((item) => (
              <div
                key={item.commitment_id}
                className="rounded-lg border border-red-200 p-3"
              >
                <p className="text-xs font-semibold text-red-700">
                  OVERDUE
                </p>
                <p className="mt-1 text-sm font-medium">
                  {item.task}
                </p>
                <p className="mt-1 text-xs text-gray-600">
                  {item.owner_name || "Unassigned"} ·{" "}
                  {item.deadline || "No date"}
                </p>
              </div>
            ))}

            {upcoming.map((item) => (
              <div
                key={item.commitment_id}
                className="rounded-lg border border-amber-200 p-3"
              >
                <p className="text-xs font-semibold text-amber-700">
                  UPCOMING
                </p>
                <p className="mt-1 text-sm font-medium">
                  {item.task}
                </p>
                <p className="mt-1 text-xs text-gray-600">
                  {item.owner_name || "Unassigned"} ·{" "}
                  {item.deadline || "No date"}
                </p>
              </div>
            ))}
          </div>

          <Link
            href="/reminders"
            className="mt-4 block rounded-lg bg-indigo-600 px-4 py-2 text-center text-sm font-medium text-white"
          >
            Manage all reminders
          </Link>
        </div>
      )}
    </div>
  );
}
