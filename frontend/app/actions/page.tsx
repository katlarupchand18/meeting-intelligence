"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";

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

export default function ActionsPage() {
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

  const loadTasks = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`${API}/api/commitments/tracker`, {
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
  }, []);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

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

    const blob = new Blob(["\uFEFF" + csv], {
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
    <main className="action-tracker-page min-h-screen bg-slate-50 px-4 py-8 text-slate-900 sm:px-8">
      <div className="mx-auto max-w-6xl">
        <Link href="/" className="text-sm text-blue-700 hover:underline">
          ← Back to Dashboard
        </Link>

        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold">Action Tracker</h1>
            <p className="mt-2 text-slate-500">
              Track responsibilities and deadlines across your meetings.
            </p>
          </div>
          <button
            onClick={() => void loadTasks()}
            className="rounded-xl border bg-white px-4 py-2 text-sm"
          >
            Refresh
          </button>
        </div>

        <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
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
            <div key={label} className="rounded-2xl border bg-white p-5 shadow-sm">
              <p className="text-sm text-slate-500">{label}</p>
              <p className="mt-2 text-3xl font-semibold">{value}</p>
            </div>
          ))}
        </div>

        <section className="mt-6 rounded-2xl border bg-white p-5">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium">Completion progress</p>
            <p className="text-sm text-slate-500">
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
            className="mt-3 h-3 overflow-hidden rounded-full bg-slate-200"
          >
            <div
              className="h-full rounded-full bg-emerald-500 transition-all"
              style={{
                width: `${
                  tasks.length
                    ? Math.round((completedCount / tasks.length) * 100)
                    : 0
                }%`,
              }}
            />
          </div>
        </section>

        <div className="mt-8 flex flex-wrap gap-3">
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search action items..."
            aria-label="Search action items"
            className="min-w-0 flex-1 rounded-xl border bg-white px-4 py-3"
          />
          <select
            value={meetingFilter}
            onChange={(event) => setMeetingFilter(event.target.value)}
            aria-label="Filter tasks by meeting"
            className="rounded-xl border bg-white px-4 py-3"
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
            className="rounded-xl border bg-white px-4 py-3"
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
            className="rounded-xl border bg-white px-4 py-3"
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
            className="rounded-xl border bg-white px-4 py-3"
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
            className="rounded-xl border bg-white px-4 py-3"
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
            className="rounded-xl border bg-white px-4 py-3"
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
          className="mt-3 text-sm text-blue-700 hover:underline"
        >
          Clear filters
        </button>

        <button
          type="button"
          onClick={exportTasksCsv}
          disabled={visibleTasks.length === 0}
          className="ml-4 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:opacity-50"
        >
          Export CSV
        </button>

        {success && (
          <p
            role="status"
            className="mt-5 rounded-xl bg-green-50 p-4 text-green-700"
          >
            {success}
          </p>
        )}

        <p className="mt-4 text-sm text-slate-500">
          Showing {visibleTasks.length} of {tasks.length} tasks
        </p>

        {savingId !== null && (
          <p role="status" className="mt-2 text-sm text-blue-700">
            Saving task changes...
          </p>
        )}

        {error && (
          <p role="alert" className="mt-5 rounded-xl bg-red-50 p-4 text-red-700">
            {error}
          </p>
        )}

        {loading ? (
          <p className="mt-10 text-slate-500">Loading action items...</p>
        ) : visibleTasks.length === 0 ? (
          <p className="mt-10 rounded-2xl border bg-white p-8 text-center text-slate-500">
            No tasks match your current filters. Try clearing the filters.
          </p>
        ) : (
          <div className="mt-6 space-y-4">
            {visibleTasks.map((task) => (
              <article key={task.id} className="rounded-2xl border bg-white p-5 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        aria-label={`Task status: ${labels[task.status]}`}
                        className={`rounded-full px-3 py-1 text-xs font-medium ${
                          task.status === "completed"
                            ? "bg-green-100 text-green-700"
                            : task.status === "in_progress"
                              ? "bg-blue-100 text-blue-700"
                              : task.status === "blocked"
                                ? "bg-orange-100 text-orange-700"
                                : "bg-slate-100 text-slate-700"
                        }`}
                      >
                        {labels[task.status]}
                      </span>
                    </div>
                    <p className="mt-3 font-medium">{task.task}</p>
                    <span
                      className={`mt-2 inline-block rounded-full px-3 py-1 text-xs font-medium ${
                        getTaskPriority(task) === "high"
                          ? "bg-red-100 text-red-700"
                          : getTaskPriority(task) === "medium"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      Priority: {getTaskPriority(task)}
                    </span>
                    <p className="mt-2 text-sm text-slate-500">
                      Deadline:
                      <input
                        type="date"
                        aria-label={`Deadline for ${task.task}`}
                        value={task.deadline || ""}
                        disabled={savingId !== null}
                        onChange={(event) =>
                          void updateField(task, "deadline", event.target.value || null)
                        }
                        className="ml-2 rounded border px-2 py-1"
                      />
                    </p>
                    <p className="mt-1 text-sm text-slate-500">
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
                      className="rounded-lg border px-3 py-2 disabled:opacity-50"
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
                    <div className="mt-3 flex items-center gap-3">
                      <Link
                        href={`/meetings/${task.meeting_id}`}
                        className="text-sm text-blue-700 hover:underline"
                      >
                        {task.meeting_title || "View source meeting"}
                      </Link>
                      {deadlineUrgency(task) && (
                        <span
                          className={`rounded-full px-3 py-1 text-xs ${
                            deadlineUrgency(task) === "Overdue"
                              ? "bg-red-100 text-red-700"
                              : deadlineUrgency(task) === "Due Today"
                                ? "bg-orange-100 text-orange-700"
                                : "bg-amber-100 text-amber-700"
                          }`}
                        >
                          {deadlineUrgency(task)}
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col items-start gap-3">
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
                      className={`rounded-lg px-3 py-2 text-sm font-medium ${
                        task.status === "completed"
                          ? "bg-slate-100 text-slate-700"
                          : "bg-emerald-600 text-white"
                      } disabled:opacity-50`}
                    >
                      {savingId === task.id
                        ? "Saving..."
                        : task.status === "completed"
                          ? "Reopen Task"
                          : "Mark Complete"}
                    </button>

                    <div>
                    <label htmlFor={`status-${task.id}`} className="mb-1 block text-xs text-slate-500">
                      Status
                    </label>
                    <select
                      id={`status-${task.id}`}
                      value={task.status === "overdue" ? "open" : task.status}
                      disabled={savingId !== null}
                      onChange={(event) =>
                        void updateStatus(task, event.target.value as Status)
                      }
                      className="rounded-lg border bg-white px-3 py-2 text-sm"
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
          </div>
        )}
      </div>
    </main>
  );
}
