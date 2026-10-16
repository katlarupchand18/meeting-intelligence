"use client";

import { useCallback, useEffect, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

export type Meeting = {
  id: string;
  title: string;
  meeting_type?: string;
  status?: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
  duration_seconds?: number;
  audio_file_path?: string;
  video_file_path?: string;
};

type MeetingsResponse = {
  items?: Meeting[];
  meetings?: Meeting[];
  total?: number;
};

export function useMeetings() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMeetings = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/meetings`, {
        method: "GET",
        headers: {
          Accept: "application/json",
        },
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error(
          `Failed to load meetings (${response.status})`
        );
      }

      const data: MeetingsResponse | Meeting[] =
        await response.json();

      if (Array.isArray(data)) {
        setMeetings(data);
      } else if (Array.isArray(data.items)) {
        setMeetings(data.items);
      } else if (Array.isArray(data.meetings)) {
        setMeetings(data.meetings);
      } else {
        setMeetings([]);
      }
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Failed to load meetings.";

      setError(message);
      setMeetings([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMeetings();
  }, [fetchMeetings]);

  return {
    meetings,
    loading,
    error,
    refresh: fetchMeetings,
  };
}