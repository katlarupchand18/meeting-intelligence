"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE_URL = "http://127.0.0.1:8000/api";
const HEALTH_URL = "http://127.0.0.1:8000/health";

export type Meeting = {
  id: string;
  title: string;
  description?: string | null;
  meeting_type?: string | null;
  status?: string | null;
  file_path?: string | null;
  file_name?: string | null;
  duration_seconds?: number | null;
  summary?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type MeetingSummary = {
  meeting_id: string;
  summary: string;
  key_topics: string[];
  decisions_count: number;
  commitments_count: number;
  evidence_count: number;
  confidence: number;
};

export type DashboardStats = {
  totalMeetings: number;
  commitments: number;
  decisions: number;
  overdue: number;
};

type ApiResponse<T> = {
  data?: T;
  success?: boolean;
  message?: string;
  detail?: string;
};

function normalizeArray<T>(value: unknown): T[] {
  if (Array.isArray(value)) {
    return value as T[];
  }

  if (
    value &&
    typeof value === "object" &&
    Array.isArray((value as { items?: unknown }).items)
  ) {
    return (value as { items: T[] }).items;
  }

  if (
    value &&
    typeof value === "object" &&
    Array.isArray((value as { meetings?: unknown }).meetings)
  ) {
    return (value as { meetings: T[] }).meetings;
  }

  return [];
}

async function fetchJson<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    cache: "no-store",
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;

    try {
      const errorBody = await response.json();

      if (typeof errorBody?.detail === "string") {
        message = errorBody.detail;
      } else if (typeof errorBody?.message === "string") {
        message = errorBody.message;
      }
    } catch {
      // Keep the default error message.
    }

    throw new Error(message);
  }

  return response.json();
}

async function checkBackendHealth(): Promise<boolean> {
  try {
    const response = await fetch(HEALTH_URL, {
      method: "GET",
      cache: "no-store",
    });

    if (!response.ok) {
      return false;
    }

    const data = await response.json();

    return (
      data?.success === true &&
      data?.status === "healthy"
    );
  } catch {
    return false;
  }
}

async function fetchMeetings(): Promise<Meeting[]> {
  const response = await fetchJson<unknown>(
    `${API_BASE_URL}/meetings`,
  );

  return normalizeArray<Meeting>(response);
}

async function fetchMeetingSummary(
  meetingId: string,
): Promise<MeetingSummary | null> {
  try {
    return await fetchJson<MeetingSummary>(
      `${API_BASE_URL}/analysis/meetings/${meetingId}/summary`,
    );
  } catch {
    return null;
  }
}

async function fetchCommitmentsCount(
  meetingId: string,
): Promise<{
  total: number;
  overdue: number;
}> {
  try {
    const response = await fetchJson<unknown>(
      `${API_BASE_URL}/commitments/meeting/${meetingId}`,
    );

    const commitments = normalizeArray<{
      status?: string;
      deadline?: string | null;
    }>(response);

    const today = new Date();

    let overdue = 0;

    for (const commitment of commitments) {
      if (
        commitment.status === "overdue"
      ) {
        overdue += 1;
        continue;
      }

      if (
        commitment.deadline &&
        new Date(commitment.deadline) < today &&
        commitment.status !== "completed" &&
        commitment.status !== "cancelled"
      ) {
        overdue += 1;
      }
    }

    return {
      total: commitments.length,
      overdue,
    };
  } catch {
    return {
      total: 0,
      overdue: 0,
    };
  }
}

export function useDashboard() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [meetingSummaries, setMeetingSummaries] =
    useState<Record<string, MeetingSummary>>({});

  const [stats, setStats] = useState<DashboardStats>({
    totalMeetings: 0,
    commitments: 0,
    decisions: 0,
    overdue: 0,
  });

  const [isOnline, setIsOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);

    const backendOnline = await checkBackendHealth();

    setIsOnline(backendOnline);

    if (!backendOnline) {
      setMeetings([]);
      setMeetingSummaries({});
      setStats({
        totalMeetings: 0,
        commitments: 0,
        decisions: 0,
        overdue: 0,
      });

      setError(
        "Backend is not reachable at http://127.0.0.1:8000",
      );

      setLoading(false);
      return;
    }

    try {
      const meetingList = await fetchMeetings();

      setMeetings(meetingList);

      const summaries: Record<string, MeetingSummary> =
        {};

      let commitmentsTotal = 0;
      let decisionsTotal = 0;
      let overdueTotal = 0;

      const summaryResults =
        await Promise.all(
          meetingList.map(async (meeting) => {
            const summary =
              await fetchMeetingSummary(
                meeting.id,
              );

            const commitments =
              await fetchCommitmentsCount(
                meeting.id,
              );

            return {
              meetingId: meeting.id,
              summary,
              commitments,
            };
          }),
        );

      for (const result of summaryResults) {
        if (result.summary) {
          summaries[result.meetingId] =
            result.summary;

          commitmentsTotal +=
            result.summary.commitments_count || 0;

          decisionsTotal +=
            result.summary.decisions_count || 0;
        }

        /*
         * If the commitments endpoint works,
         * use its real count. Otherwise the
         * analysis summary count remains available.
         */
        if (result.commitments.total > 0) {
          const existing =
            summaries[result.meetingId];

          if (existing) {
            const difference =
              result.commitments.total -
              existing.commitments_count;

            commitmentsTotal += difference;
          } else {
            commitmentsTotal +=
              result.commitments.total;
          }
        }

        overdueTotal +=
          result.commitments.overdue;
      }

      setMeetingSummaries(summaries);

      setStats({
        totalMeetings: meetingList.length,
        commitments: Math.max(
          0,
          commitmentsTotal,
        ),
        decisions: Math.max(
          0,
          decisionsTotal,
        ),
        overdue: Math.max(
          0,
          overdueTotal,
        ),
      });

      setIsOnline(true);
    } catch (err) {
      console.error(
        "Dashboard loading failed:",
        err,
      );

      setError(
        err instanceof Error
          ? err.message
          : "Failed to load dashboard data.",
      );

      /*
       * Backend health worked, so keep the
       * application marked online even if a
       * secondary API request failed.
       */
      setIsOnline(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  return {
    meetings,
    meetingSummaries,
    stats,
    isOnline,
    loading,
    error,
    refresh: loadDashboard,
  };
}