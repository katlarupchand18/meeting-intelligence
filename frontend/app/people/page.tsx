"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Meeting = {
  id: string;
  title: string;
  created_at: string | null;
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
  assigned_count: number;
  completed_count: number;
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

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "Unknown date";
  try {
    const date = new Date(dateStr);
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "Unknown date";
  }
}

export default function PeoplePage() {
  const router = useRouter();
  const [people, setPeople] = useState<Person[]>([]);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [selectedPersonId, setSelectedPersonId] = useState("");
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

    if (!selectedPersonId) return;

    void loadPerson(selectedPersonId).catch((err) => {
      setError(err instanceof Error ? err.message : "Unable to load person.");
    });
  }, [selectedPersonId, loadPerson]);

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
      setSelectedPersonId(created.id);
      setNewName("");
      setMessage(`Created shared identity: ${created.display_name}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create person.");
    } finally {
      setSaving(false);
    }
  }

  async function linkParticipant() {
    const person = people.find((item) => item.id === selectedPersonId);
    const meeting = meetings.find((item) => item.id === meetingId);
    const participant = participants.find((item) => item.id === participantId);

    if (!person || !meeting || !participant) {
      setError("Select a person, meeting, and participant.");
      return;
    }

    if (participant.person_id && participant.person_id !== selectedPersonId) {
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
        `/api/people/${selectedPersonId}/participants/${participantId}`,
        { method: "POST" }
      );

      await Promise.all([
        loadPerson(selectedPersonId),
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
    const person = people.find((item) => item.id === selectedPersonId);

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
        `/api/people/${selectedPersonId}/participants/${participant.id}`,
        { method: "DELETE" }
      );

      await loadPerson(selectedPersonId);

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
    <main className="page-wrapper">
      <Link href="/" className="back-link">
        ← Dashboard
      </Link>

      <h1>People & Identity Management</h1>

      <p className="text-slate-500">
        View shared identities and their linked meeting participants. Select a person to see their assigned work across all meetings.
      </p>

      {error && (
        <p role="alert" className="meeting-alert meeting-alert-error" style={{ marginTop: 16 }}>
          {error}
        </p>
      )}

      {message && (
        <p role="status" className="meeting-alert meeting-alert-success" style={{ marginTop: 16 }}>
          {message}
        </p>
      )}

      {loading ? (
        <p className="text-slate-500 mt-8">Loading people and meetings...</p>
      ) : (
        <>
          {/* Person Selector / Dashboard */}
          <section className="meeting-card" style={{ marginTop: 24 }}>
            <div className="meeting-card-heading">
              <div>
                <span className="eyebrow">PERSON DASHBOARD</span>
                <h2>Select a Person</h2>
              </div>
            </div>

            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 8 }}>
              <select
                value={selectedPersonId}
                onChange={(event) => setSelectedPersonId(event.target.value)}
                className="meeting-search"
                style={{ minWidth: 300, flex: 1 }}
              >
                <option value="">Select a person to view their details</option>
                {people.map((person) => (
                  <option key={person.id} value={person.id}>
                    {person.display_name}
                  </option>
                ))}
              </select>

              {selectedPersonId && (
                <button
                  onClick={() => router.push(`/actions?person_id=${selectedPersonId}`)}
                  className="primary-button"
                  style={{ alignSelf: "flex-end" }}
                >
                  View Assigned Work →
                </button>
              )}
            </div>
          </section>

          {/* Person Detail */}
          {selectedPersonId && personDetail && (
            <section className="meeting-card" style={{ marginTop: 24 }}>
              <div className="meeting-card-heading">
                <div>
                  <span className="eyebrow">PERSON DETAILS</span>
                  <h2>{personDetail.display_name}</h2>
                </div>
              </div>

              <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", marginTop: 16 }}>
                <div style={{ background: "#eff6ff", border: "1px solid #bfdbfe", borderRadius: 8, padding: 16, minWidth: 180 }}>
                  <p style={{ fontSize: 12, color: "#1e40af" }}>Assigned Tasks</p>
                  <p style={{ fontSize: 24, fontWeight: 700, color: "#2563eb" }}>{personDetail.assigned_count || 0}</p>
                </div>
                <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", borderRadius: 8, padding: 16, minWidth: 180 }}>
                  <p style={{ fontSize: 12, color: "#166534" }}>Completed Tasks</p>
                  <p style={{ fontSize: 24, fontWeight: 700, color: "#16a34a" }}>{personDetail.completed_count || 0}</p>
                </div>
                <div style={{ background: "#fef3c7", border: "1px solid #fde68a", borderRadius: 8, padding: 16, minWidth: 180 }}>
                  <p style={{ fontSize: 12, color: "#92400e" }}>Pending Tasks</p>
                  <p style={{ fontSize: 24, fontWeight: 700, color: "#d97706" }}>{(personDetail.assigned_count || 0) - (personDetail.completed_count || 0)}</p>
                </div>
                <div style={{ background: "#fce7f3", border: "1px solid #fbcfe8", borderRadius: 8, padding: 16, minWidth: 180 }}>
                  <p style={{ fontSize: 12, color: "#9d174d" }}>Linked Meetings</p>
                  <p style={{ fontSize: 24, fontWeight: 700, color: "#be185d" }}>{personDetail.participants.length}</p>
                </div>
              </div>

              <button
                onClick={() => router.push(`/actions?person_id=${selectedPersonId}`)}
                className="primary-button"
                style={{ marginTop: 16 }}
              >
                View Assigned Work →
              </button>

              <h3 style={{ marginTop: 24, fontSize: 16, fontWeight: 600 }}>Linked Meeting Participants</h3>

              {personDetail.participants.length === 0 ? (
                <p style={{ marginTop: 12, color: "#64748b" }}>No participants linked yet.</p>
              ) : (
                <ul style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 12 }}>
                  {personDetail.participants.map((participant) => {
                    const meeting = meetings.find(m => m.id === participant.meeting_id);
                    return (
                      <li
                        key={participant.id}
                        onClick={() => meeting && router.push(`/meetings/${meeting.id}`)}
                        style={{
                          border: "1px solid #e2e8f0",
                          padding: 16,
                          borderRadius: 8,
                          display: "flex",
                          justifyContent: "space-between",
                          gap: 12,
                          flexWrap: "wrap",
                          cursor: "pointer",
                          transition: "background 0.2s",
                          background: "#fff",
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.background = "#fafafa"}
                        onMouseLeave={(e) => e.currentTarget.style.background = "#fff"}
                      >
                        <div>
                          <strong>{participant.name}</strong>
                          <p style={{ fontSize: 12, color: "#64748b", marginTop: 4 }}>
                            {meeting ? meeting.title : `Meeting ID: ${participant.meeting_id}`}
                          </p>
                          <p style={{ fontSize: 11, color: "#94a3b8" }}>
                            {meeting ? formatDate(meeting.created_at) : ""}
                          </p>
                        </div>

                        <button
                          disabled={saving}
                          onClick={(e) => { e.stopPropagation(); void unlinkParticipant(participant); }}
                          style={{
                            padding: "8px 14px",
                            borderRadius: 8,
                            border: "1px solid #ef4444",
                            color: "#ef4444",
                            cursor: "pointer",
                          }}
                        >
                          Unlink
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          )}

          {/* Manage Identities Section */}
          <section className="meeting-card" style={{ marginTop: 24 }}>
            <div className="meeting-card-heading">
              <div>
                <span className="eyebrow">MANAGE IDENTITIES</span>
                <h2>Create & Link Shared Identities</h2>
              </div>
            </div>

            <div style={{ borderTop: "1px solid #e2e8f0", paddingTop: 24, marginTop: 8 }}>
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
                    border: "1px solid #cbd5e1",
                    borderRadius: 8,
                    color: "inherit",
                    background: "transparent",
                    fontSize: 16,
                  }}
                />

                <button
                  onClick={() => void createPerson()}
                  disabled={saving || !newName.trim()}
                  className="primary-button"
                  style={{ padding: "12px 20px" }}
                >
                  Create Person
                </button>
              </div>

              <div style={{ marginTop: 24 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Link Participant to Identity</h3>

                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 16 }}>
                  <label>
                    Shared person
                    <select
                      value={selectedPersonId}
                      onChange={(event) => setSelectedPersonId(event.target.value)}
                      className="meeting-search"
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
                      className="meeting-search"
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
                      className="meeting-search"
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
                  disabled={saving || !selectedPersonId || !meetingId || !participantId}
                  className="primary-button"
                  style={{ marginTop: 16 }}
                >
                  Confirm & Link Participant
                </button>
              </div>
            </div>
          </section>
        </>
      )}
    </main>
  );
}