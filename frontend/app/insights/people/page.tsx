"use client";

import { useCallback, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Person = {
  id: string;
  display_name: string;
};

type Meeting = {
  id: string;
  title: string;
  summary: string | null;
  created_at: string | null;
};

type Participant = {
  id: string;
  meeting_id: string;
  name: string;
  role: string | null;
  organization: string | null;
  speaker_label: string | null;
};

type Task = {
  id: string;
  meeting_id: string;
  participant_id: string;
  task: string;
  status: string;
  deadline: string | null;
  deadline_text: string | null;
  overdue: boolean;
  verification_status: string;
};

type Statistics = {
  total_meetings: number;
  total_participant_records: number;
  total_tasks: number;
  pending_tasks: number;
  completed_tasks: number;
  cancelled_tasks: number;
  overdue_tasks: number;
  completion_rate: number;
};

type Insights = {
  person: Person;
  statistics: Statistics;
  meetings: Meeting[];
  participants: Participant[];
  tasks: Task[];
  requires_review: boolean;
};

export default function CrossMeetingInsightsPage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [personId, setPersonId] = useState("");
  const [insights, setInsights] = useState<Insights | null>(null);
  const [loadingPeople, setLoadingPeople] = useState(true);
  const [loadingInsights, setLoadingInsights] = useState(false);
  const [error, setError] = useState("");

  const loadPeople = useCallback(async () => {
    setLoadingPeople(true);
    setError("");

    try {
      const response = await fetch(`${API}/api/people`, {
        cache: "no-store",
      });

      if (!response.ok) {
        throw new Error("Failed to load shared identities.");
      }

      const data = await response.json();
      const items: Person[] = Array.isArray(data.people)
        ? data.people
        : [];

      setPeople(items);
      setPersonId((current) =>
        items.some((person) => person.id === current)
          ? current
          : items[0]?.id || ""
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load people."
      );
    } finally {
      setLoadingPeople(false);
    }
  }, []);

  useEffect(() => {
    void loadPeople();
  }, [loadPeople]);

  useEffect(() => {
    if (!personId) {
      setInsights(null);
      return;
    }

    let cancelled = false;

    async function loadInsights() {
      setLoadingInsights(true);
      setError("");
      setInsights(null);

      try {
        const response = await fetch(
          `${API}/api/insights/people/${personId}`,
          { cache: "no-store" }
        );

        if (!response.ok) {
          throw new Error(
            response.status === 404
              ? "This shared identity no longer exists."
              : "Failed to load cross-meeting insights."
          );
        }

        const data: Insights = await response.json();

        if (!cancelled) {
          setInsights(data);
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Failed to load insights."
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingInsights(false);
        }
      }
    }

    void loadInsights();

    return () => {
      cancelled = true;
    };
  }, [personId]);

  const meetingNames = new Map(
    insights?.meetings.map((meeting) => [
      meeting.id,
      meeting.title,
    ]) || []
  );

  const cards = insights
    ? [
        ["Meetings", insights.statistics.total_meetings],
        ["Assigned tasks", insights.statistics.total_tasks],
        ["Pending", insights.statistics.pending_tasks],
        ["Completed", insights.statistics.completed_tasks],
        ["Overdue", insights.statistics.overdue_tasks],
        ["Completion rate", `${insights.statistics.completion_rate}%`],
      ]
    : [];

  return (
    <main
      style={{
        maxWidth: 1100,
        margin: "0 auto",
        padding: "40px 20px",
      }}
    >
      <nav style={{ display: "flex", gap: 20, marginBottom: 24 }}>
        <a href="/">Dashboard</a>
        <a href="/people">People &amp; Identities</a>
        <a href="/insights">Participant Insights</a>
      </nav>

      <h1 style={{ fontSize: 32, fontWeight: 700 }}>
        Cross-Meeting Intelligence
      </h1>

      <p style={{ marginTop: 10, opacity: 0.75 }}>
        Review a confirmed person&apos;s meeting history,
        responsibilities, and accountability across meetings.
      </p>

      <section style={{ marginTop: 28 }}>
        <label htmlFor="person" style={{ display: "block", marginBottom: 8 }}>
          Select a confirmed person
        </label>

        <select
          id="person"
          value={personId}
          onChange={(event) => setPersonId(event.target.value)}
          disabled={loadingPeople || people.length === 0}
          style={{
            width: "100%",
            maxWidth: 420,
            padding: 12,
            border: "1px solid #888",
            borderRadius: 8,
            background: "transparent",
            color: "inherit",
          }}
        >
          {people.length === 0 && (
            <option value="">No shared identities yet</option>
          )}

          {people.map((person) => (
            <option key={person.id} value={person.id}>
              {person.display_name}
            </option>
          ))}
        </select>
      </section>

      {error && (
        <p role="alert" style={{ marginTop: 20, color: "#dc2626" }}>
          {error}
        </p>
      )}

      {loadingPeople && <p style={{ marginTop: 24 }}>Loading people...</p>}

      {!loadingPeople && people.length === 0 && !error && (
        <section style={{ marginTop: 28 }}>
          <p>
            No shared identities have been created yet.
            Create a person and manually link their meeting
            participants before viewing combined insights.
          </p>
          <p style={{ marginTop: 12 }}>
            <a href="/people">Manage People &amp; Identities</a>
          </p>
        </section>
      )}

      {loadingInsights && (
        <p style={{ marginTop: 24 }}>Loading cross-meeting insights...</p>
      )}

      {insights && !loadingInsights && (
        <>
          <h2 style={{ fontSize: 24, marginTop: 32 }}>
            {insights.person.display_name}
          </h2>

          <div
            style={{
              display: "grid",
              gridTemplateColumns:
                "repeat(auto-fit, minmax(150px, 1fr))",
              gap: 14,
              marginTop: 20,
            }}
          >
            {cards.map(([label, value]) => (
              <div
                key={label}
                style={{
                  border: "1px solid #8885",
                  borderRadius: 12,
                  padding: 18,
                }}
              >
                <div style={{ opacity: 0.7 }}>{label}</div>
                <div
                  style={{
                    fontSize: 26,
                    fontWeight: 700,
                    marginTop: 8,
                  }}
                >
                  {value}
                </div>
              </div>
            ))}
          </div>

          <section style={{ marginTop: 36 }}>
            <h2 style={{ fontSize: 22 }}>Meeting History</h2>

            {insights.meetings.length === 0 ? (
              <p style={{ marginTop: 12 }}>
                No meeting participants linked to this person.
              </p>
            ) : (
              <ul style={{ marginTop: 16, paddingLeft: 20 }}>
                {insights.meetings.map((meeting) => (
                  <li key={meeting.id} style={{ marginBottom: 14 }}>
                    <strong>{meeting.title}</strong>
                    {meeting.created_at && (
                      <div style={{ opacity: 0.65, fontSize: 13 }}>
                        {new Date(meeting.created_at).toLocaleDateString()}
                      </div>
                    )}
                    <div style={{ opacity: 0.75, marginTop: 4 }}>
                      {
                        insights.participants
                          .filter((p) => p.meeting_id === meeting.id)
                          .map((p) =>
                            p.role ? `${p.name} (${p.role})` : p.name
                          )
                          .join(", ")
                      }
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section style={{ marginTop: 36 }}>
            <h2 style={{ fontSize: 22 }}>Assigned Commitments</h2>

            {insights.tasks.length === 0 ? (
              <p style={{ marginTop: 12 }}>
                No assigned commitments found.
              </p>
            ) : (
              <div style={{ display: "grid", gap: 14, marginTop: 16 }}>
                {insights.tasks.map((task) => (
                  <article
                    key={task.id}
                    style={{
                      border: "1px solid #8885",
                      borderRadius: 12,
                      padding: 18,
                    }}
                  >
                    <h3 style={{ fontWeight: 600 }}>{task.task}</h3>

                    <p style={{ marginTop: 8, opacity: 0.75 }}>
                      Meeting:{" "}
                      {meetingNames.get(task.meeting_id) ||
                        "Unknown meeting"}
                    </p>

                    <p style={{ marginTop: 6 }}>
                      Status: <strong>{task.status}</strong>
                      {task.overdue && (
                        <strong style={{ color: "#dc2626" }}>
                          {" "}· Overdue
                        </strong>
                      )}
                    </p>

                    <p style={{ marginTop: 6, opacity: 0.75 }}>
                      Deadline:{" "}
                      {task.deadline ||
                        task.deadline_text ||
                        "Not specified"}
                    </p>

                    <p style={{ marginTop: 6, opacity: 0.75 }}>
                      Verification: {task.verification_status}
                    </p>
                  </article>
                ))}
              </div>
            )}
          </section>

          <p style={{ marginTop: 32, opacity: 0.65, fontSize: 13 }}>
            These insights use manually linked identities.
            AI-extracted commitments and identity assignments
            may require human review.
          </p>
        </>
      )}
    </main>
  );
}
