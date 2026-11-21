"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Meeting = {
  id: string;
  title: string;
};

type Participant = {
  id: string;
  meeting_id: string;
  name: string;
  person_id?: string | null;
};

type Person = {
  id: string;
  display_name: string;
  created_at: string | null;
};

type PersonDetail = Person & {
  participants: Participant[];
  total_participants: number;
};

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    cache: "no-store",
    ...options,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status})`
    );
  }

  return response.json() as Promise<T>;
}

export default function PeoplePage() {
  const [people, setPeople] = useState<Person[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [personId, setPersonId] = useState("");
  const [meetingId, setMeetingId] = useState("");
  const [participantId, setParticipantId] = useState("");
  const [personDetail, setPersonDetail] = useState<PersonDetail | null>(null);
  const [newName, setNewName] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const loadPeople = useCallback(async () => {
    const data = await request<{ people: Person[] }>("/api/people");
    setPeople(data.people);
    return data.people;
  }, []);

  const loadMeetings = useCallback(async () => {
    const data = await request<
      Meeting[] | { items?: Meeting[]; meetings?: Meeting[] }
    >("/api/meetings?page=1&page_size=100");

    const items = Array.isArray(data)
      ? data
      : data.items ?? data.meetings ?? [];

    setMeetings(items);
  }, []);

  const loadPerson = useCallback(async (id: string) => {
    if (!id) {
      setPersonDetail(null);
      return;
    }

    const data = await request<PersonDetail>(`/api/people/${id}`);
    setPersonDetail(data);
  }, []);

  const loadParticipants = useCallback(async (id: string) => {
    if (!id) {
      setParticipants([]);
      return;
    }

    const data = await request<{ participants: Participant[] }>(
      `/api/participants/meeting/${id}`
    );

    setParticipants(data.participants);
  }, []);

  useEffect(() => {
    let active = true;

    async function initialize() {
      try {
        const [peopleData, meetingsData] = await Promise.all([
          request<{ people: Person[] }>("/api/people"),
          request<
            Meeting[] | { items?: Meeting[]; meetings?: Meeting[] }
          >("/api/meetings?page=1&page_size=100"),
        ]);

        if (!active) return;

        setPeople(peopleData.people);

        const items = Array.isArray(meetingsData)
          ? meetingsData
          : meetingsData.items ?? meetingsData.meetings ?? [];

        setMeetings(items);
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to load data.");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    void initialize();

    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    setParticipantId("");
    setParticipants([]);

    if (!meetingId) return;

    void loadParticipants(meetingId).catch((err) => {
      setError(err instanceof Error ? err.message : "Unable to load participants.");
    });
  }, [meetingId, loadParticipants]);

  useEffect(() => {
    setPersonDetail(null);

    if (!personId) return;

    void loadPerson(personId).catch((err) => {
      setError(err instanceof Error ? err.message : "Unable to load person.");
    });
  }, [personId, loadPerson]);

  async function createPerson() {
    const name = newName.trim();

    if (!name) {
      setError("Enter a person's display name.");
      return;
    }

    setSaving(true);
    setError("");
    setMessage("");

    try {
      const created = await request<Person>("/api/people", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: name }),
      });

      await loadPeople();
      setPersonId(created.id);
      setNewName("");
      setMessage(`Created shared identity: ${created.display_name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create person.");
    } finally {
      setSaving(false);
    }
  }

  async function linkParticipant() {
    const person = people.find((item) => item.id === personId);
    const meeting = meetings.find((item) => item.id === meetingId);
    const participant = participants.find((item) => item.id === participantId);

    if (!person || !meeting || !participant) {
      setError("Select a person, meeting, and participant.");
      return;
    }

    if (participant.person_id && participant.person_id !== personId) {
      setError("This participant belongs to another identity. Unlink it first.");
      return;
    }

    const confirmed = window.confirm(
      `Confirm these records represent the same real person?\n\n` +
      `Shared identity: ${person.display_name}\n` +
      `Meeting: ${meeting.title}\n` +
      `Participant: ${participant.name}\n\n` +
      `This link will affect future cross-meeting insights.`
    );

    if (!confirmed) return;

    setSaving(true);
    setError("");
    setMessage("");

    try {
      await request(
        `/api/people/${personId}/participants/${participantId}`,
        { method: "POST" }
      );

      await Promise.all([
        loadPerson(personId),
        loadParticipants(meetingId),
      ]);

      setMessage(`Linked ${participant.name} to ${person.display_name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to link participant.");
    } finally {
      setSaving(false);
    }
  }

  async function unlinkParticipant(participant: Participant) {
    const person = people.find((item) => item.id === personId);

    if (!person) return;

    const confirmed = window.confirm(
      `Unlink ${participant.name} from ${person.display_name}?\n\n` +
      `The original meeting participant and commitments will remain.`
    );

    if (!confirmed) return;

    setSaving(true);
    setError("");
    setMessage("");

    try {
      await request(
        `/api/people/${personId}/participants/${participant.id}`,
        { method: "DELETE" }
      );

      await loadPerson(personId);

      if (meetingId) {
        await loadParticipants(meetingId);
      }

      setMessage(`Unlinked ${participant.name}.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to unlink participant.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <main style={{
      maxWidth: 1000,
      margin: "0 auto",
      padding: "40px 20px",
      color: "var(--foreground)",
    }}>
<div style={{ marginBottom: 20 }}><a href="/insights/people">Cross-Meeting Insights</a></div>
      <Link href="/" style={{ textDecoration: "underline" }}>
        ← Back to Dashboard
      </Link>

      <h1 style={{ fontSize: 32, fontWeight: 700, marginTop: 24 }}>
        People & Identity Management
      </h1>

      <p style={{ margin: "12px 0 28px", opacity: 0.75 }}>
        Connect meeting participants to shared identities only after
        confirming they are the same real person.
      </p>

      {error && (
        <p role="alert" style={{ color: "#dc2626", marginBottom: 16 }}>
          {error}
        </p>
      )}

      {message && (
        <p role="status" style={{ color: "#16a34a", marginBottom: 16 }}>
          {message}
        </p>
      )}

      {loading ? (
        <p>Loading people and meetings...</p>
      ) : (
        <>
          <section style={{
            border: "1px solid #8885",
            borderRadius: 12,
            padding: 24,
            marginBottom: 24,
          }}>
            <h2 style={{ fontSize: 22, fontWeight: 600 }}>
              1. Create a Shared Person
            </h2>

            <div style={{ display: "flex", gap: 12, marginTop: 16, flexWrap: "wrap" }}>
              <input
                aria-label="New person's name"
                value={newName}
                onChange={(event) => setNewName(event.target.value)}
                placeholder="Full name"
                maxLength={255}
                style={{
                  flex: 1,
                  minWidth: 180,
                  padding: 12,
                  border: "1px solid #8887",
                  borderRadius: 8,
                  color: "inherit",
                  background: "transparent",
                }}
              />

              <button
                onClick={() => void createPerson()}
                disabled={saving || !newName.trim()}
                style={{
                  padding: "12px 20px",
                  borderRadius: 8,
                  background: "#2563eb",
                  color: "white",
                  cursor: "pointer",
                }}
              >
                Create Person
              </button>
            </div>
          </section>

          <section style={{
            border: "1px solid #8885",
            borderRadius: 12,
            padding: 24,
            marginBottom: 24,
          }}>
            <h2 style={{ fontSize: 22, fontWeight: 600 }}>
              2. Select Records to Link
            </h2>

            <div style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
              gap: 16,
              marginTop: 16,
            }}>
              <label>
                Shared person
                <select
                  value={personId}
                  onChange={(event) => setPersonId(event.target.value)}
                  style={{ display: "block", width: "100%", padding: 12, marginTop: 8 }}
                >
                  <option value="">Select a person</option>
                  {people.map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.display_name}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Meeting
                <select
                  value={meetingId}
                  onChange={(event) => setMeetingId(event.target.value)}
                  style={{ display: "block", width: "100%", padding: 12, marginTop: 8 }}
                >
                  <option value="">Select a meeting</option>
                  {meetings.map((meeting) => (
                    <option key={meeting.id} value={meeting.id}>
                      {meeting.title}
                    </option>
                  ))}
                </select>
              </label>

              <label>
                Meeting participant
                <select
                  value={participantId}
                  onChange={(event) => setParticipantId(event.target.value)}
                  disabled={!meetingId}
                  style={{ display: "block", width: "100%", padding: 12, marginTop: 8 }}
                >
                  <option value="">Select a participant</option>
                  {participants.map((participant) => (
                    <option key={participant.id} value={participant.id}>
                      {participant.name}
                      {participant.person_id ? " (linked)" : ""}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <button
              onClick={() => void linkParticipant()}
              disabled={saving || !personId || !meetingId || !participantId}
              style={{
                marginTop: 20,
                padding: "12px 20px",
                borderRadius: 8,
                background: "#2563eb",
                color: "white",
                cursor: "pointer",
              }}
            >
              Confirm & Link Participant
            </button>
          </section>

          <section style={{
            border: "1px solid #8885",
            borderRadius: 12,
            padding: 24,
          }}>
            <h2 style={{ fontSize: 22, fontWeight: 600 }}>
              3. Linked Meeting Records
            </h2>

            {!personId ? (
              <p style={{ marginTop: 12 }}>
                Select a shared person to view their linked participants.
              </p>
            ) : !personDetail ? (
              <p style={{ marginTop: 12 }}>Loading linked records...</p>
            ) : personDetail.participants.length === 0 ? (
              <p style={{ marginTop: 12 }}>No participants linked yet.</p>
            ) : (
              <ul style={{ marginTop: 16, display: "grid", gap: 12 }}>
                {personDetail.participants.map((participant) => (
                  <li
                    key={participant.id}
                    style={{
                      border: "1px solid #8885",
                      padding: 16,
                      borderRadius: 8,
                      display: "flex",
                      justifyContent: "space-between",
                      gap: 12,
                      flexWrap: "wrap",
                    }}
                  >
                    <div>
                      <strong>{participant.name}</strong>
                      <p style={{ fontSize: 12, opacity: 0.7 }}>
                        Meeting ID: {participant.meeting_id}
                      </p>
                    </div>

                    <button
                      disabled={saving}
                      onClick={() => void unlinkParticipant(participant)}
                      style={{
                        padding: "8px 14px",
                        borderRadius: 8,
                        border: "1px solid #dc2626",
                        color: "#dc2626",
                        cursor: "pointer",
                      }}
                    >
                      Unlink
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </>
      )}
    </main>
  );
}
