"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Status =
  | "open"
  | "in_progress"
  | "completed"
  | "blocked"
  | "overdue"
  | "cancelled";

type Commitment = {
  id: string;
  meeting_id: string;
  meeting_title: string;
  owner_name: string | null;
  owner_id: string | null;
  task: string;
  deadline: string | null;
  deadline_text: string | null;
  status: Status;
  notes: string | null;
};

type ParticipantOption = {
  id: string;
  name: string;
};

const labels: Record<Status, string> = {
  open: "Pending",
  in_progress: "In Progress",
  completed: "Completed",
  blocked: "Blocked",
  overdue: "Overdue",
  cancelled: "Cancelled",
};

const statuses: Status[] = [
  "open",
  "in_progress",
  "completed",
  "blocked",
  "cancelled",
];

function isOverdue(task: Commitment) {
  if (
    task.status === "completed" ||
    task.status === "cancelled"
  ) {
    return false;
  }

  if (!task.deadline) {
    return task.status === "overdue";
  }

  const today = new Date();

  const localToday = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");

  return task.deadline < localToday;
}

function deadlineUrgency(task: Commitment): string | null {
  if (task.status === "completed" || task.status === "cancelled") {
    return null;
  }

  if (isOverdue(task)) return "Overdue";
  if (!task.deadline) return null;

  const today = new Date();
  const localToday = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");

  const start = new Date(`${localToday}T12:00:00`);
  const due = new Date(`${task.deadline}T12:00:00`);
  const days = Math.round(
    (due.getTime() - start.getTime()) / 86400000
  );

  if (days === 0) return "Due Today";
  if (days > 0 && days <= 3) return "Due Soon";
  return null;
}

function matchesDeadlineFilter(
  task: Commitment,
  filter: string
): boolean {
  if (filter === "all") return true;
  if (filter === "no_deadline") return !task.deadline;
  if (filter === "overdue") return isOverdue(task);
  if (!task.deadline) return false;

  const today = new Date();
  const localToday = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");

  if (filter === "today") return task.deadline === localToday;

  if (filter === "next_7_days") {
    const start = new Date(`${localToday}T12:00:00`);
    const due = new Date(`${task.deadline}T12:00:00`);
    const days = Math.round(
      (due.getTime() - start.getTime()) / 86400000
    );
    return days >= 0 && days <= 7;
  }

  return true;
}

type TaskPriority = "high" | "medium" | "low";

function getTaskPriority(task: Commitment): TaskPriority {
  if (task.status === "completed" || task.status === "cancelled") {
    return "low";
  }

  if (isOverdue(task) || task.status === "blocked") {
    return "high";
  }

  if (!task.deadline) return "low";

  const today = new Date();
  const start = new Date(
    today.getFullYear(),
    today.getMonth(),
    today.getDate()
  );

  const [year, month, day] = task.deadline.split("-").map(Number);
  const due = new Date(year, month - 1, day);

  const days = Math.round(
    (due.getTime() - start.getTime()) / 86400000
  );

  if (days <= 1) return "high";
  if (days <= 7) return "medium";

  return "low";
}

function ActionsPageContent() {
  const searchParams = useSearchParams();
  const personId = searchParams.get("person_id");

  const [tasks, setTasks] = useState<Commitment[]>([]);
  const [filter, setFilter] = useState("all");
  const [meetingFilter, setMeetingFilter] = useState("all");
  const [sortBy, setSortBy] = useState("newest");
  const [ownerFilter, setOwnerFilter] = useState("all");
  const [deadlineFilter, setDeadlineFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [participants, setParticipants] = useState<
    Record<string, ParticipantOption[]>
  >({});
  const [people, setPeople] = useState<Array<{id: string, display_name: string}>>([]);

  const loadPeople = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/people`, { cache: "no-store" });
      if (response.ok) {
        const data = await response.json();
        setPeople(data.people || []);
      }
    } catch (err) {
      console.error('Failed to load people:', err);
    }
  }, []);

  useEffect(() => {
    void loadPeople();
  }, [loadPeople]);

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      let url = `${API}/api/commitments/tracker`;
      if (personId) {
        url = `${API}/api/commitments/tracker/person/${personId}`;
      }
      const response = await fetch(url, {
        cache: "no-store",
      });
      if (!response.ok) throw new Error(`Failed to load tasks (${response.status})`);
      const data: Commitment[] = await response.json();
      setTasks(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load tasks.");
    } finally {
      setLoading(false);
    }
  }, [personId]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  // Auto-select person in owner filter if person_id is in URL
  useEffect(() => {
    if (personId) {
      setOwnerFilter(personId);
    }
  }, [personId]);

  async function updateField(
    task: Commitment,
    field: "deadline" | "owner_id",
    value: string | null
  ) {
    if (savingId !== null) return;
    setSavingId(task.id);
    setError("");
    setSuccess("");

    try {
      const response = await fetch(`${API}/api/commitments/${task.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [field]: value }),
      });

      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(
          typeof detail?.detail === "string"
            ? detail.detail
            : `Update failed (${response.status})`
        );
      }

      await loadTasks();
      setSuccess("Task updated successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed.");
    } finally {
      setSavingId(null);
    }
  }

  async function loadParticipants(meetingId: string) {
    if (participants[meetingId]) return;

    try {
      const response = await fetch(
        `${API}/api/participants/meeting/${meetingId}`
      );
      if (!response.ok) throw new Error("Could not load participants.");

      const data = await response.json();
      const options = Array.isArray(data)
        ? data
        : Array.isArray(data.participants)
          ? data.participants
          : [];

      setParticipants((previous) => ({
        ...previous,
        [meetingId]: options,
      }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load participants.");
    }
  }

  async function updateStatus(task: Commitment, status: Status) {
    if (savingId !== null) return;
    setSavingId(task.id);
    setError("");
    setSuccess("");
    try {
      const response = await fetch(`${API}/api/commitments/${task.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      if (!response.ok) {
        const detail = await response.json().catch(() => null);
        throw new Error(
          typeof detail?.detail === "string"
            ? detail.detail
            : `Status update failed (${response.status})`
        );
      }
      await loadTasks();
      setSuccess("Task status updated successfully.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update task.");
    } finally {
      setSavingId(null);
    }
  }

  const meetingOptions = useMemo(() => {
    const unique = new Map<string, string>();

    for (const task of tasks) {
      unique.set(task.meeting_id, task.meeting_title);
    }

    return Array.from(unique.entries()).sort((a, b) =>
      a[1].localeCompare(b[1])
    );
  }, [tasks]);

  const ownerOptions = useMemo(() => {
    const owners = new Map<string, string>();

    for (const task of tasks) {
      if (task.owner_id) {
        owners.set(task.owner_id, task.owner_name || "Unknown owner");
      }
    }

    return Array.from(owners.entries()).sort((a, b) =>
      a[1].localeCompare(b[1])
    );
  }, [tasks]);

  const visibleTasks = useMemo(() => {
    const filtered = tasks.filter((task) => {
      const matchesSearch =
        task.task.toLowerCase().includes(search.toLowerCase()) ||
        (task.notes || "").toLowerCase().includes(search.toLowerCase());

      const matchesStatus =
        filter === "all" ||
        (filter === "active"
          ? task.status !== "completed" && task.status !== "cancelled"
          : filter === "overdue"
          ? isOverdue(task)
          : filter === "open"
            ? task.status === "open" && !isOverdue(task)
            : task.status === filter);

      const matchesMeeting =
        meetingFilter === "all" ||
        task.meeting_id === meetingFilter;

      const matchesOwner =
        ownerFilter === "all" ||
        (ownerFilter === "unassigned"
          ? !task.owner_id
          : task.owner_id === ownerFilter);

      const matchesDeadline = matchesDeadlineFilter(task, deadlineFilter);

      const matchesPriority =
        priorityFilter === "all" ||
        getTaskPriority(task) === priorityFilter;

      return matchesSearch && matchesStatus && matchesMeeting &&
        matchesOwner && matchesDeadline && matchesPriority;
    });

    return filtered.sort((a, b) => {
      if (sortBy === "priority") {
        const rank = { high: 0, medium: 1, low: 2 };
        const difference =
          rank[getTaskPriority(a)] - rank[getTaskPriority(b)];

        if (difference !== 0) return difference;

        return (a.deadline || "9999-12-31").localeCompare(
          b.deadline || "9999-12-31"
        );
      }

      if (sortBy === "name") {
        return a.task.localeCompare(b.task);
      }

      if (sortBy === "deadline") {
        return (a.deadline || "9999-12-31").localeCompare(
          b.deadline || "9999-12-31"
        );
      }

      if (sortBy === "oldest") {
        return tasks.indexOf(b) - tasks.indexOf(a);
      }

      return tasks.indexOf(a) - tasks.indexOf(b);
    });
  }, [
    tasks,
    filter,
    search,
    meetingFilter,
    sortBy,
    ownerFilter,
    deadlineFilter,
    priorityFilter,
  ]);

  function exportTasksCsv() {
    const columns = [
      "Task", "Meeting", "Owner", "Status",
      "Deadline", "Overdue",
    ];

    const escapeCsv = (value: string) =>
      `"${value.replace(/"/g, '""')}"`;

    const rows = visibleTasks.map((task) => [
      task.task,
      task.meeting_title,
      task.owner_name || "Unassigned",
      task.status,
      task.deadline || task.deadline_text || "",
      isOverdue(task) ? "Yes" : "No",
    ]);

    const csv = [columns, ...rows]
      .map((row) => row.map(escapeCsv).join(","))
      .join("\r\n");

    const blob = new Blob(["﻿" + csv], {
      type: "text/csv;charset=utf-8",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "meeting-action-tracker.csv";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  const overdueCount = tasks.filter(isOverdue).length;
  const completedCount = tasks.filter((task) => task.status === "completed").length;
  const inProgressCount = tasks.filter(
    (task) => task.status === "in_progress"
  ).length;
  const blockedCount = tasks.filter(
    (task) => task.status === "blocked"
  ).length;
  const unassignedCount = tasks.filter(
    (task) => !task.owner_id
  ).length;
  const highPriorityCount = tasks.filter(
    (task) => getTaskPriority(task) === "high"
  ).length;
  const mediumPriorityCount = tasks.filter(
    (task) => getTaskPriority(task) === "medium"
  ).length;
  const lowPriorityCount = tasks.filter(
    (task) => getTaskPriority(task) === "low"
  ).length;
  const pendingCount = tasks.filter((task) => task.status === "open" && !isOverdue(task)).length;

  return (
    <main className="page-wrapper">
      <Link href="/" className="back-link">
        ← Dashboard
      </Link>

      <h1>Action Tracker</h1>

      <p className="text-slate-500">
        Track responsibilities and deadlines across your meetings.
      </p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 16, alignItems: "center", justifyContent: "space-between", marginTop: 24 }}>
        <div></div>
        <button
          onClick={() => void loadTasks()}
          className="primary-button"
          style={{ padding: "10px 16px", fontSize: 14 }}
        >
          Refresh
        </button>
      </div>

      {/* Summary Stats */}
      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">OVERVIEW</span>
            <h2>Summary Statistics</h2>
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 16, marginTop: 16 }}>
          {[
            ["Total Tasks", tasks.length],
            ["Pending", pendingCount],
            ["In Progress", inProgressCount],
            ["Completed", completedCount],
            ["Overdue", overdueCount],
            ["Blocked", blockedCount],
            ["Unassigned", unassignedCount],
            ["High Priority", highPriorityCount],
            ["Medium Priority", mediumPriorityCount],
            ["Low Priority", lowPriorityCount],
          ].map(([label, value]) => (
            <div key={label} style={{ border: "1px solid #e2e8f0", borderRadius: 12, padding: 20, background: "#fff" }}>
              <p style={{ fontSize: 13, color: "#64748b" }}>{label}</p>
              <p style={{ marginTop: 8, fontSize: 28, fontWeight: 700 }}>{value}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Completion Progress */}
      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">PROGRESS</span>
            <h2>Completion Progress</h2>
          </div>
        </div>
        <div style={{ marginTop: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
            <p style={{ fontWeight: 500 }}>Completion progress</p>
            <p style={{ color: "#64748b" }}>
              {tasks.length
                ? Math.round((completedCount / tasks.length) * 100)
                : 0}%
            </p>
          </div>
          <div
            role="progressbar"
            aria-label="Task completion progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={
              tasks.length
                ? Math.round((completedCount / tasks.length) * 100)
                : 0
            }
            style={{ height: 10, borderRadius: 9999, background: "#e2e8f0", overflow: "hidden" }}
          >
            <div
              style={{
                height: "100%",
                borderRadius: 9999,
                background: "#10b981",
                transition: "width 0.3s",
                width: `${
                  tasks.length
                    ? Math.round((completedCount / tasks.length) * 100)
                    : 0
                }%`,
              }}
            />
          </div>
        </div>
      </section>

      {/* Filters */}
      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">FILTERS</span>
            <h2>Filter & Sort</h2>
          </div>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 16 }}>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search action items..."
            aria-label="Search action items"
            className="meeting-search"
            style={{ minWidth: 200, flex: 1 }}
          />
          <select
            value={personId || ""}
            onChange={(event) => {
              const newPersonId = event.target.value;
              if (newPersonId) {
                window.location.href = `/actions?person_id=${newPersonId}`;
              } else {
                window.location.href = `/actions`;
              }
            }}
            aria-label="Filter tasks by person"
            className="meeting-search"
            style={{ minWidth: 180 }}
          >
            <option value="">All people</option>
            {people.map((person) => (
              <option key={person.id} value={person.id}>
                {person.display_name}
              </option>
            ))}
          </select>

          <select
            value={meetingFilter}
            onChange={(event) => setMeetingFilter(event.target.value)}
            aria-label="Filter tasks by meeting"
            className="meeting-search"
            style={{ minWidth: 180 }}
          >
            <option value="all">All meetings</option>
            {meetingOptions.map(([id, title]) => (
              <option key={id} value={id}>
                {title}
              </option>
            ))}
          </select>

          <select
            value={ownerFilter}
            onChange={(event) => setOwnerFilter(event.target.value)}
            aria-label="Filter tasks by owner"
            className="meeting-search"
            style={{ minWidth: 180 }}
          >
            <option value="all">All owners</option>
            <option value="unassigned">Unassigned</option>
            {ownerOptions.map(([id, name]) => (
              <option key={id} value={id}>
                {name}
              </option>
            ))}
          </select>

          <select
            value={deadlineFilter}
            onChange={(event) => setDeadlineFilter(event.target.value)}
            aria-label="Filter tasks by deadline"
            className="meeting-search"
            style={{ minWidth: 160 }}
          >
            <option value="all">All deadlines</option>
            <option value="overdue">Overdue</option>
            <option value="today">Due today</option>
            <option value="next_7_days">Next 7 days</option>
            <option value="no_deadline">No deadline</option>
          </select>

          <select
            value={priorityFilter}
            onChange={(event) => setPriorityFilter(event.target.value)}
            aria-label="Filter tasks by priority"
            className="meeting-search"
            style={{ minWidth: 160 }}
          >
            <option value="all">All priorities</option>
            <option value="high">High priority</option>
            <option value="medium">Medium priority</option>
            <option value="low">Low priority</option>
          </select>

          <select
            value={sortBy}
            onChange={(event) => setSortBy(event.target.value)}
            aria-label="Sort tasks"
            className="meeting-search"
            style={{ minWidth: 160 }}
          >
            <option value="newest">Newest first</option>
            <option value="priority">Highest priority first</option>
            <option value="oldest">Oldest first</option>
            <option value="deadline">Deadline first</option>
            <option value="name">Task name A–Z</option>
          </select>

          <select
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            aria-label="Filter tasks by status"
            className="meeting-search"
            style={{ minWidth: 160 }}
          >
            <option value="all">All statuses</option>
            <option value="active">Active tasks</option>
            <option value="open">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="completed">Completed</option>
            <option value="blocked">Blocked</option>
            <option value="overdue">Overdue</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <div style={{ display: "flex", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
          <button
            type="button"
            onClick={() => {
              setSearch("");
              setFilter("all");
              setMeetingFilter("all");
              setSortBy("newest");
              setOwnerFilter("all");
              setDeadlineFilter("all");
              setPriorityFilter("all");
            }}
            style={{
              padding: "10px 16px",
              border: "1px solid #cbd5e1",
              borderRadius: 8,
              background: "transparent",
              cursor: "pointer",
              fontSize: 14,
            }}
          >
            Clear filters
          </button>

          <button
            type="button"
            onClick={exportTasksCsv}
            disabled={visibleTasks.length === 0}
            className="primary-button"
            style={{ padding: "10px 16px", fontSize: 14, opacity: visibleTasks.length === 0 ? 0.5 : 1 }}
          >
            Export CSV
          </button>
        </div>
      </section>

      {success && (
        <p role="status" className="meeting-alert meeting-alert-success" style={{ marginTop: 16 }}>
          {success}
        </p>
      )}

      <p style={{ marginTop: 16, fontSize: 14, color: "#64748b" }}>
        Showing {visibleTasks.length} of {tasks.length} tasks
      </p>

      {savingId !== null && (
        <p role="status" className="meeting-alert" style={{ marginTop: 12, background: "#eff6ff", borderColor: "#bfdbfe", color: "#1d4ed8" }}>
          Saving task changes...
        </p>
      )}

      {error && (
        <p role="alert" className="meeting-alert meeting-alert-error" style={{ marginTop: 16 }}>
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-slate-500 mt-8">Loading action items...</p>
      ) : visibleTasks.length === 0 ? (
        <p className="text-slate-500 mt-12 text-center">No tasks match your current filters. Try clearing the filters.</p>
      ) : (
        <section style={{ marginTop: 24 }}>
          {visibleTasks.map((task) => (
            <article key={task.id} className="meeting-card" style={{ marginTop: 16 }}>
              <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 16 }}>
                <div style={{ flex: 1, minWidth: 300 }}>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                    <span
                      aria-label={`Task status: ${labels[task.status]}`}
                      style={{
                        padding: "4px 10px",
                        borderRadius: 9999,
                        fontSize: 12,
                        fontWeight: 600,
                        background:
                          task.status === "completed"
                            ? "#dcfce7"
                            : task.status === "in_progress"
                            ? "#dbeafe"
                            : task.status === "blocked"
                            ? "#ffedd5"
                            : "#f1f5f9",
                        color:
                          task.status === "completed"
                            ? "#166534"
                            : task.status === "in_progress"
                            ? "#1d4ed8"
                            : task.status === "blocked"
                            ? "#9a3412"
                            : "#475569",
                      }}
                    >
                      {labels[task.status]}
                    </span>
                  </div>
                  <p style={{ fontSize: 18, fontWeight: 600 }}>{task.task}</p>
                  <span
                    style={{
                      marginTop: 8,
                      display: "inline-block",
                      padding: "4px 10px",
                      borderRadius: 9999,
                      fontSize: 12,
                      fontWeight: 600,
                      background:
                        getTaskPriority(task) === "high"
                          ? "#fef2f2"
                          : getTaskPriority(task) === "medium"
                          ? "#fffbeb"
                          : "#f1f5f9",
                      color:
                        getTaskPriority(task) === "high"
                          ? "#991b1b"
                          : getTaskPriority(task) === "medium"
                          ? "#92400e"
                          : "#64748b",
                    }}
                  >
                    Priority: {getTaskPriority(task)}
                  </span>
                  <p style={{ marginTop: 10, fontSize: 14, color: "#64748b" }}>
                    Deadline:
                    <input
                      type="date"
                      aria-label={`Deadline for ${task.task}`}
                      value={task.deadline || ""}
                      disabled={savingId !== null}
                      onChange={(event) =>
                        void updateField(task, "deadline", event.target.value || null)
                      }
                      style={{
                        marginLeft: 8,
                        padding: "6px 10px",
                        border: "1px solid #cbd5e1",
                        borderRadius: 8,
                        color: "inherit",
                        background: "transparent",
                        fontSize: 14,
                      }}
                    />
                  </p>
                  <p style={{ marginTop: 6, fontSize: 14, color: "#64748b" }}>
                    Owner:
                    <select
                      value={task.owner_id || ""}
                      onFocus={() => void loadParticipants(task.meeting_id)}
                      onChange={(event) =>
                        void updateField(
                          task,
                          "owner_id",
                          event.target.value || null
                        )
                      }
                      disabled={savingId !== null}
                      aria-label={`Owner for ${task.task}`}
                      style={{
                        marginLeft: 8,
                        padding: "8px 12px",
                        border: "1px solid #cbd5e1",
                        borderRadius: 8,
                        color: "inherit",
                        background: "transparent",
                        fontSize: 14,
                      }}
                    >
                      <option value="">Unassigned</option>
                      {task.owner_id &&
                        !(participants[task.meeting_id] || []).some(
                          (person) => person.id === task.owner_id
                        ) && (
                          <option value={task.owner_id}>
                            {task.owner_name || "Current owner"}
                          </option>
                        )}
                      {(participants[task.meeting_id] || []).map((person) => (
                        <option key={person.id} value={person.id}>
                          {person.name}
                        </option>
                      ))}
                    </select>
                  </p>
                  <div style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
                    <Link
                      href={`/meetings/${task.meeting_id}`}
                      style={{ fontSize: 14, color: "#2563eb" }}
                    >
                      {task.meeting_title || "View source meeting"}
                    </Link>
                    {deadlineUrgency(task) && (
                      <span
                        style={{
                          padding: "4px 10px",
                          borderRadius: 9999,
                          fontSize: 11,
                          fontWeight: 600,
                          background:
                            deadlineUrgency(task) === "Overdue"
                              ? "#fef2f2"
                              : deadlineUrgency(task) === "Due Today"
                              ? "#fff7ed"
                              : "#fffbeb",
                          color:
                            deadlineUrgency(task) === "Overdue"
                              ? "#991b1b"
                              : deadlineUrgency(task) === "Due Today"
                              ? "#9a3412"
                              : "#92400e",
                        }}
                      >
                        {deadlineUrgency(task)}
                      </span>
                    )}
                  </div>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 200 }}>
                  <button
                    type="button"
                    disabled={savingId !== null}
                    onClick={() => {
                      if (
                        task.status === "completed" &&
                        !window.confirm(
                          "Reopen this completed task?"
                        )
                      ) {
                        return;
                      }
                      void updateStatus(
                        task,
                        task.status === "completed" ? "open" : "completed"
                      );
                    }}
                    style={{
                      padding: "10px 16px",
                      borderRadius: 8,
                      fontSize: 14,
                      fontWeight: 500,
                      cursor: savingId !== null ? "wait" : "pointer",
                      background:
                        task.status === "completed"
                          ? "#f1f5f9"
                          : "#10b981",
                      color:
                        task.status === "completed"
                          ? "#475569"
                          : "#fff",
                      border: "none",
                      opacity: savingId !== null ? 0.6 : 1,
                    }}
                  >
                    {savingId === task.id
                      ? "Saving..."
                      : task.status === "completed"
                      ? "Reopen Task"
                      : "Mark Complete"}
                  </button>

                  <div>
                    <label htmlFor={`status-${task.id}`} style={{ display: "block", fontSize: 12, color: "#64748b", marginBottom: 4 }}>
                      Status
                    </label>
                    <select
                      id={`status-${task.id}`}
                      value={task.status === "overdue" ? "open" : task.status}
                      disabled={savingId !== null}
                      onChange={(event) =>
                        void updateStatus(task, event.target.value as Status)
                      }
                      className="meeting-search"
                      style={{ padding: "8px 12px", fontSize: 14 }}
                    >
                      {statuses.map((status) => (
                        <option key={status} value={status}>
                          {labels[status]}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}

export default function ActionsPage() {
  return (
    <Suspense fallback={<main style={{ padding: 32 }}>Loading action tracker...</main>}>
      <ActionsPageContent />
    </Suspense>
  );
}