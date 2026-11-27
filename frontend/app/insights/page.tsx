"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

const API =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Summary = {
  total_commitments: number;
  completed: number;
  in_progress: number;
  blocked: number;
  pending: number;
  overdue: number;
  cancelled: number;
  unassigned: number;
  completion_rate: number;
  overdue_rate: number;
  total_meetings: number;
  meetings_with_commitments: number;
};

type MeetingStat = {
  meeting_id: string;
  meeting_title: string;
  total_commitments: number;
  completed: number;
  overdue: number;
  completion_rate: number;
};

type WorkloadStat = {
  person_id: string;
  person_name: string;
  total_commitments: number;
  completed: number;
  overdue: number;
  completion_rate: number;
};

type InsightsData = {
  summary: Summary;
  meetings: MeetingStat[];
  workload: WorkloadStat[];
};

function StatCard({ label, value, color = "slate" }: { label: string; value: number | string; color?: string }) {
  const colors: Record<string, string> = {
    slate: "bg-slate-100 text-slate-700",
    green: "bg-green-100 text-green-700",
    red: "bg-red-100 text-red-700",
    blue: "bg-blue-100 text-blue-700",
    amber: "bg-amber-100 text-amber-700",
    purple: "bg-purple-100 text-purple-700",
  };

  return (
    <div className="rounded-2xl border bg-white p-5 shadow-sm">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="mt-2 text-3xl font-semibold">{value}</p>
    </div>
  );
}

function ProgressBar({ value, label, color = "emerald" }: { value: number; label: string; color?: string }) {
  const colors: Record<string, string> = {
    emerald: "bg-emerald-500",
    red: "bg-red-500",
    amber: "bg-amber-500",
    blue: "bg-blue-500",
  };

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-sm">
        <span>{label}</span>
        <span className="font-semibold">{value}%</span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-slate-200">
        <div
          className={`h-full rounded-full transition-all ${colors[color]}`}
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
        />
      </div>
    </div>
  );
}

function MeetingRow({ meeting }: { meeting: MeetingStat }) {
  return (
    <tr className="border-t border-slate-100 hover:bg-slate-50">
      <td className="px-4 py-3">
        <Link href={`/meetings/${meeting.meeting_id}`} className="font-medium text-blue-700 hover:underline">
          {meeting.meeting_title}
        </Link>
      </td>
      <td className="px-4 py-3 text-center">{meeting.total_commitments}</td>
      <td className="px-4 py-3 text-center text-green-700">{meeting.completed}</td>
      <td className="px-4 py-3 text-center text-red-700">{meeting.overdue}</td>
      <td className="px-4 py-3 text-center font-semibold">{meeting.completion_rate}%</td>
    </tr>
  );
}

function WorkloadRow({ person }: { person: WorkloadStat }) {
  return (
    <tr className="border-t border-slate-100 hover:bg-slate-50">
      <td className="px-4 py-3 font-medium">{person.person_name}</td>
      <td className="px-4 py-3 text-center">{person.total_commitments}</td>
      <td className="px-4 py-3 text-center text-green-700">{person.completed}</td>
      <td className="px-4 py-3 text-center text-red-700">{person.overdue}</td>
      <td className="px-4 py-3 text-center font-semibold">{person.completion_rate}%</td>
    </tr>
  );
}

export default function InsightsPage() {
  const [insights, setInsights] = useState<InsightsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadInsights = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/insights/overview`, { cache: "no-store" });
      if (!response.ok) throw new Error("Failed to load insights");
      const data: InsightsData = await response.json();
      setInsights(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load insights");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadInsights();
  }, [loadInsights]);

  if (loading) {
    return (
      <main className="page-wrapper">
        <div className="flex items-center justify-center h-64">
          <p className="text-slate-500">Loading insights...</p>
        </div>
      </main>
    );
  }

  if (error) {
    return (
      <main className="page-wrapper">
        <p role="alert" className="meeting-alert meeting-alert-error">{error}</p>
      </main>
    );
  }

  if (!insights) {
    return (
      <main className="page-wrapper">
        <p className="text-slate-500">No data available.</p>
      </main>
    );
  }

  const { summary, meetings, workload } = insights;

  return (
    <main className="page-wrapper">
      <Link href="/" className="back-link">
        ← Dashboard
      </Link>

      <h1>Cross-Meeting Insights</h1>

      <p className="text-slate-500">
        Overall completion rates, overdue tracking, and workload distribution across all meetings.
      </p>

      {/* Summary Stats */}
      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">OVERVIEW</span>
            <h2>Summary Statistics</h2>
          </div>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-6" style={{ marginTop: 16 }}>
          <StatCard label="Total Commitments" value={summary.total_commitments} />
          <StatCard label="Completed" value={summary.completed} color="green" />
          <StatCard label="In Progress" value={summary.in_progress} color="blue" />
          <StatCard label="Overdue" value={summary.overdue} color="red" />
          <StatCard label="Unassigned" value={summary.unassigned} color="amber" />
          <StatCard label="Total Meetings" value={summary.total_meetings} color="purple" />
        </div>
      </section>

      {/* Key Rates */}
      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">RATES</span>
            <h2>Key Rates</h2>
          </div>
        </div>
        <div className="grid gap-6 md:grid-cols-2" style={{ marginTop: 16 }}>
          <div>
            <h3 className="font-semibold text-slate-700">Completion Rate</h3>
            <ProgressBar value={summary.completion_rate} label={`${summary.completed} of ${summary.total_commitments - summary.cancelled} active commitments`} color="emerald" />
            <p className="mt-2 text-sm text-slate-500">
              {summary.cancelled} cancelled commitments excluded from rate calculation.
            </p>
          </div>
          <div>
            <h3 className="font-semibold text-slate-700">Overdue Rate</h3>
            <ProgressBar value={summary.overdue_rate} label={`${summary.overdue} of ${summary.total_commitments - summary.cancelled} active commitments`} color="red" />
            <p className="mt-2 text-sm text-slate-500">
              Based on confirmed deadlines that have passed.
            </p>
          </div>
        </div>
      </section>

      {/* Workload Distribution */}
      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">WORKLOAD</span>
            <h2>Workload Distribution (by Person)</h2>
          </div>
        </div>
        <p className="mt-2 text-sm text-slate-500">
          Shows committed tasks per person across all meetings. Only includes people with linked identities.
        </p>
        {workload.length === 0 ? (
          <p className="mt-4 text-slate-500">No workload data available. Link participants to people identities first.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Person</th>
                  <th className="px-4 py-3 text-center">Total</th>
                  <th className="px-4 py-3 text-center">Completed</th>
                  <th className="px-4 py-3 text-center">Overdue</th>
                  <th className="px-4 py-3 text-center">Completion Rate</th>
                </tr>
              </thead>
              <tbody>
                {workload.map((person) => (
                  <WorkloadRow key={person.person_id} person={person} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* Meeting-wise Statistics */}
      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">MEETINGS</span>
            <h2>Meeting-Wise Statistics</h2>
          </div>
        </div>
        <p className="mt-2 text-sm text-slate-500">
          Commitment breakdown per meeting. Click a meeting title to view details.
        </p>
        {meetings.length === 0 ? (
          <p className="mt-4 text-slate-500">No meeting statistics available.</p>
        ) : (
          <div className="mt-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  <th className="px-4 py-3">Meeting</th>
                  <th className="px-4 py-3 text-center">Total Commitments</th>
                  <th className="px-4 py-3 text-center">Completed</th>
                  <th className="px-4 py-3 text-center">Overdue</th>
                  <th className="px-4 py-3 text-center">Completion Rate</th>
                </tr>
              </thead>
              <tbody>
                {meetings.map((meeting) => (
                  <MeetingRow key={meeting.meeting_id} meeting={meeting} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}