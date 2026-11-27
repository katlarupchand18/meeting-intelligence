"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";

const API =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Meeting = {
  id: string;
  title: string;
  created_at: string | null;
};

type ComparisonData = {
  meeting_a: Meeting & { date: string };
  meeting_b: Meeting & { date: string };
  commitments: {
    new_commitments: Array<{
      task: string;
      status: string;
      deadline: string | null;
      deadline_text: string | null;
      owner: string | null;
    }>;
    completed_commitments: Array<{
      task: string;
      meeting_a_status: string;
      meeting_b_status: string;
      meeting_a_deadline: string | null;
      meeting_b_deadline: string | null;
    }>;
    pending_commitments: Array<{
      task: string;
      status: string;
      deadline: string | null;
      owner: string | null;
    }>;
    changed_deadlines: Array<{
      task: string;
      meeting_a_deadline: string | null;
      meeting_b_deadline: string | null;
      meeting_a_deadline_text: string | null;
      meeting_b_deadline_text: string | null;
    }>;
    changed_ownership: Array<{
      task: string;
      meeting_a_owner: string | null;
      meeting_b_owner: string | null;
    }>;
    not_mentioned_again: Array<{
      task: string;
      status: string;
      deadline: string | null;
      deadline_text: string | null;
      owner: string | null;
    }>;
  };
  decisions: {
    new_decisions: Array<{
      title: string;
      description: string;
      status: string;
    }>;
    changed_decisions: Array<{
      title: string;
      meeting_a_description: string;
      meeting_b_description: string;
      meeting_a_status: string;
      meeting_b_status: string;
    }>;
    superseded_decisions: Array<{
      title: string;
      meeting_a_status: string;
      meeting_b_status: string;
    }>;
    not_mentioned_again: Array<{
      title: string;
      description: string;
      status: string;
    }>;
  };
  relevant_excerpts: Array<{
    meeting_id: string;
    meeting_title: string;
    speaker: string | null;
    text: string;
    start_time: number;
    end_time: number;
  }>;
  followup_questions: string[];
  summary: string;
};

type Suggestion = {
  meeting_id: string;
  title: string;
  date: string;
  shared_participants: string[];
  score: number;
};

function formatDate(dateStr: string): string {
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

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-green-100 text-green-700",
    open: "bg-slate-100 text-slate-700",
    in_progress: "bg-blue-100 text-blue-700",
    blocked: "bg-orange-100 text-orange-700",
    overdue: "bg-red-100 text-red-700",
    cancelled: "bg-gray-100 text-gray-700",
    accepted: "bg-green-100 text-green-700",
    proposed: "bg-blue-100 text-blue-700",
    rejected: "bg-red-100 text-red-700",
    changed: "bg-amber-100 text-amber-700",
    superseded: "bg-purple-100 text-purple-700",
  };
  return (
    <span className={`rounded-full px-2 py-1 text-xs font-medium ${colors[status] || "bg-slate-100 text-slate-700"}`}>
      {status.replace("_", " ")}
    </span>
  );
}

function CommitmentSection({ title, items, emptyMessage }: { title: string; items: any[]; emptyMessage: string }) {
  if (items.length === 0) return null;
  return (
    <section className="meeting-card" style={{ marginTop: 16 }}>
      <div className="meeting-card-heading">
        <div>
          <span className="eyebrow">COMMITMENTS</span>
          <h3>{title} ({items.length})</h3>
        </div>
      </div>
      <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        {items.map((item, index) => (
          <div key={index} style={{ border: "1px solid #e2e8f0", padding: 16, borderRadius: 8, background: "#fff" }}>
            <p style={{ fontWeight: 500 }}>{item.task || item.title}</p>
            {item.status && <StatusBadge status={item.status} />}
            {item.meeting_a_status && item.meeting_b_status && (
              <p style={{ marginTop: 6, fontSize: 13, color: "#64748b" }}>
                Status: <span style={{ fontWeight: 500 }}>{item.meeting_a_status}</span> → <span style={{ fontWeight: 500 }}>{item.meeting_b_status}</span>
              </p>
            )}
            {item.meeting_a_deadline !== undefined && item.meeting_b_deadline !== undefined && (
              <p style={{ marginTop: 6, fontSize: 13, color: "#64748b" }}>
                Deadline: <span style={{ fontWeight: 500 }}>{item.meeting_a_deadline || item.meeting_a_deadline_text || "Not set"}</span> → <span style={{ fontWeight: 500 }}>{item.meeting_b_deadline || item.meeting_b_deadline_text || "Not set"}</span>
              </p>
            )}
            {item.meeting_a_owner !== undefined && item.meeting_b_owner !== undefined && (
              <p style={{ marginTop: 6, fontSize: 13, color: "#64748b" }}>
                Owner: <span style={{ fontWeight: 500 }}>{item.meeting_a_owner || "Unassigned"}</span> → <span style={{ fontWeight: 500 }}>{item.meeting_b_owner || "Unassigned"}</span>
              </p>
            )}
            {item.deadline && !item.meeting_a_deadline && (
              <p style={{ marginTop: 6, fontSize: 13, color: "#64748b" }}>Deadline: {item.deadline}</p>
            )}
            {item.owner && !item.meeting_a_owner && (
              <p style={{ marginTop: 6, fontSize: 13, color: "#64748b" }}>Owner: {item.owner}</p>
            )}
            {item.description && (
              <p style={{ marginTop: 6, fontSize: 13, color: "#64748b" }}>{item.description}</p>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}

export default function CompareMeetingsPage() {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [meetingAId, setMeetingAId] = useState("");
  const [meetingBId, setMeetingBId] = useState("");
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [comparison, setComparison] = useState<ComparisonData | null>(null);
  const [loading, setLoading] = useState(false);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [error, setError] = useState("");
  const [showEmail, setShowEmail] = useState(false);

  const loadMeetings = useCallback(async () => {
    try {
      const response = await fetch(`${API}/api/meetings?page=1&page_size=100`, { cache: "no-store" });
      if (response.ok) {
        const data = await response.json();
        const items = Array.isArray(data) ? data : data.items ?? data.meetings ?? [];
        setMeetings(items);
      }
    } catch (err) {
      console.error('Failed to load meetings:', err);
    }
  }, []);

  useEffect(() => {
    void loadMeetings();
  }, [loadMeetings]);

  const loadSuggestions = useCallback(async () => {
    if (!meetingAId) {
      setSuggestions([]);
      return;
    }
    setLoadingSuggestions(true);
    try {
      const response = await fetch(`${API}/api/comparison/suggestions?meeting_id=${meetingAId}`, { cache: "no-store" });
      if (response.ok) {
        const data = await response.json();
        setSuggestions(data.suggestions || []);
      }
    } catch (err) {
      console.error('Failed to load suggestions:', err);
    } finally {
      setLoadingSuggestions(false);
    }
  }, [meetingAId]);

  useEffect(() => {
    void loadSuggestions();
  }, [loadSuggestions]);

  const handleCompare = async () => {
    if (!meetingAId || !meetingBId || meetingAId === meetingBId) return;

    setLoading(true);
    setError("");
    setComparison(null);

    try {
      const response = await fetch(
        `${API}/api/comparison/compare?meeting_a_id=${meetingAId}&meeting_b_id=${meetingBId}`,
        { cache: "no-store" }
      );

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || `Comparison failed (${response.status})`);
      }

      const data: ComparisonData = await response.json();
      setComparison(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSwap = () => {
    setMeetingAId(meetingBId);
    setMeetingBId(meetingAId);
  };

  return (
    <main className="page-wrapper">
      <Link href="/followups" className="back-link">
        ← Back to Follow-ups
      </Link>

      <h1>Compare Meetings</h1>

      <p className="text-slate-500">
        Compare two meetings to detect changes in commitments, decisions, and follow-up items.
      </p>

      {/* Meeting Selection */}
      <section className="meeting-card" style={{ marginTop: 24 }}>
        <div className="meeting-card-heading">
          <div>
            <span className="eyebrow">SELECT MEETINGS</span>
            <h2>Select Meetings to Compare</h2>
          </div>
        </div>

        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", marginTop: 16 }}>
          <div>
            <label style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 6, color: "#374151" }}>
              Earlier Meeting (Meeting A)
            </label>
            <select
              value={meetingAId}
              onChange={(e) => setMeetingAId(e.target.value)}
              className="meeting-search"
            >
              <option value="">Select meeting</option>
              {meetings.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title} ({formatDate(m.created_at || "")})
                </option>
              ))}
            </select>
          </div>

          <div style={{ display: "flex", alignItems: "flex-end" }}>
            <button
              onClick={handleSwap}
              disabled={!meetingAId || !meetingBId}
              style={{
                padding: 12,
                border: "1px solid #cbd5e1",
                borderRadius: 8,
                background: "#fff",
                cursor: "pointer",
                opacity: !meetingAId || !meetingBId ? 0.5 : 1,
              }}
              title="Swap meetings"
            >
              <svg width="24" height="24" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" />
              </svg>
            </button>
          </div>

          <div>
            <label style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 6, color: "#374151" }}>
              Later Meeting (Meeting B)
            </label>
            <select
              value={meetingBId}
              onChange={(e) => setMeetingBId(e.target.value)}
              className="meeting-search"
            >
              <option value="">Select meeting</option>
              {meetings.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.title} ({formatDate(m.created_at || "")})
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Suggestions */}
        {meetingAId && suggestions.length > 0 && (
          <div className="meeting-card" style={{ marginTop: 16, background: "#eff6ff", borderColor: "#bfdbfe" }}>
            <p style={{ fontWeight: 500, color: "#1e40af", marginBottom: 8 }}>Suggested related meetings for Meeting A:</p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
              {suggestions.slice(0, 5).map((s) => (
                <button
                  key={s.meeting_id}
                  onClick={() => setMeetingBId(s.meeting_id)}
                  style={{
                    padding: "8px 12px",
                    borderRadius: 6,
                    background: "#dbeafe",
                    color: "#1e40af",
                    fontSize: 13,
                    border: "none",
                    cursor: "pointer",
                  }}
                >
                  {s.title} ({s.shared_participants.length} shared)
                </button>
              ))}
            </div>
          </div>
        )}

        <button
          onClick={handleCompare}
          disabled={!meetingAId || !meetingBId || loading}
          className="primary-button"
          style={{ marginTop: 16 }}
        >
          {loading ? "Comparing..." : "Compare Meetings"}
        </button>

        {error && <p className="meeting-alert meeting-alert-error" style={{ marginTop: 16 }}>{error}</p>}
      </section>

      {/* Comparison Results */}
      {comparison && (
        <>
          {/* Summary */}
          <section className="meeting-card" style={{ marginTop: 24 }}>
            <div className="meeting-card-heading">
              <div>
                <span className="eyebrow">SUMMARY</span>
                <h2>Comparison Summary</h2>
              </div>
            </div>
            <p style={{ marginTop: 16, color: "#475569" }}>{comparison.summary}</p>
          </section>

          {/* Commitments Comparison */}
          <section className="meeting-card" style={{ marginTop: 24 }}>
            <div className="meeting-card-heading">
              <div>
                <span className="eyebrow">COMMITMENTS</span>
                <h2>Commitments Comparison</h2>
              </div>
            </div>

            <CommitmentSection
              title="New Commitments (in Meeting B only)"
              items={comparison.commitments.new_commitments}
              emptyMessage="No new commitments"
            />
            <CommitmentSection
              title="Completed Commitments (done in A, still open in B)"
              items={comparison.commitments.completed_commitments}
              emptyMessage="No completed commitments re-opened"
            />
            <CommitmentSection
              title="Pending Commitments (still active in B)"
              items={comparison.commitments.pending_commitments}
              emptyMessage="No pending commitments"
            />
            <CommitmentSection
              title="Changed Deadlines"
              items={comparison.commitments.changed_deadlines}
              emptyMessage="No deadline changes"
            />
            <CommitmentSection
              title="Changed Ownership"
              items={comparison.commitments.changed_ownership}
              emptyMessage="No ownership changes"
            />
            <CommitmentSection
              title="Not Mentioned Again (from Meeting A)"
              items={comparison.commitments.not_mentioned_again.filter(c => c.status !== "completed" && c.status !== "cancelled")}
              emptyMessage="All commitments from Meeting A were addressed"
            />
          </section>

          {/* Decisions Comparison */}
          <section className="meeting-card" style={{ marginTop: 24 }}>
            <div className="meeting-card-heading">
              <div>
                <span className="eyebrow">DECISIONS</span>
                <h2>Decisions Comparison</h2>
              </div>
            </div>

            <CommitmentSection
              title="New Decisions (in Meeting B only)"
              items={comparison.decisions.new_decisions}
              emptyMessage="No new decisions"
            />
            <CommitmentSection
              title="Changed Decisions"
              items={comparison.decisions.changed_decisions}
              emptyMessage="No decision changes"
            />
            <CommitmentSection
              title="Superseded Decisions"
              items={comparison.decisions.superseded_decisions}
              emptyMessage="No superseded decisions"
            />
            <CommitmentSection
              title="Not Mentioned Again (from Meeting A)"
              items={comparison.decisions.not_mentioned_again}
              emptyMessage="All decisions from Meeting A were referenced"
            />
          </section>

          {/* Relevant Transcript Excerpts */}
          {comparison.relevant_excerpts.length > 0 && (
            <section className="meeting-card" style={{ marginTop: 24 }}>
              <div className="meeting-card-heading">
                <div>
                  <span className="eyebrow">EXCERPTS</span>
                  <h2>Relevant Transcript Excerpts</h2>
                </div>
              </div>
              <p style={{ marginTop: 8, fontSize: 14, color: "#64748b" }}>
                Key excerpts from both meetings related to commitments and decisions.
              </p>
              <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 12 }}>
                {comparison.relevant_excerpts.map((excerpt, index) => (
                  <div key={index} style={{ border: "1px solid #e2e8f0", padding: 16, borderRadius: 8, background: "#fafafa" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8, flexWrap: "wrap", gap: 8 }}>
                      <span style={{ fontWeight: 500 }}>{excerpt.meeting_title}</span>
                      <span style={{ fontSize: 13, color: "#64748b" }}>
                        {excerpt.speaker || "Unknown"} • {Math.floor(excerpt.start_time / 60)}:{String(excerpt.start_time % 60).padStart(2, "0")}
                      </span>
                    </div>
                    <p style={{ fontSize: 14, color: "#334155" }}>{excerpt.text}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Follow-up Questions */}
          {comparison.followup_questions.length > 0 && (
            <section className="meeting-card" style={{ marginTop: 24 }}>
              <div className="meeting-card-heading">
                <div>
                  <span className="eyebrow">FOLLOW-UP</span>
                  <h2>Recommended Follow-up Questions</h2>
                </div>
              </div>
              <ol style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 8, paddingLeft: 20 }}>
                {comparison.followup_questions.map((q, index) => (
                  <li key={index} style={{ color: "#334155" }}>{q}</li>
                ))}
              </ol>
            </section>
          )}

          {/* Generate Follow-up Email */}
          <section className="meeting-card" style={{ marginTop: 24 }}>
            <div className="meeting-card-heading">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
                <div>
                  <span className="eyebrow">EMAIL</span>
                  <h2>Generate Follow-up Email</h2>
                </div>
                <button
                  onClick={() => setShowEmail(!showEmail)}
                  className="primary-button"
                  style={{ padding: "10px 16px", fontSize: 14 }}
                >
                  {showEmail ? "Hide Email Draft" : "Show Email Draft"}
                </button>
              </div>
            </div>

            {showEmail && (
              <div style={{ marginTop: 16, display: "flex", flexDirection: "column", gap: 16 }}>
                <div>
                  <label style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 6, color: "#374151" }}>Subject</label>
                  <input
                    type="text"
                    defaultValue={`Follow-up: ${comparison.meeting_b.title}`}
                    className="meeting-search"
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 6, color: "#374151" }}>Body</label>
                  <textarea
                    defaultValue={generateEmailBody(comparison)}
                    rows={15}
                    className="meeting-search"
                    style={{ fontFamily: "monospace", fontSize: 13, minHeight: 280 }}
                  />
                </div>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}

function generateEmailBody(comparison: ComparisonData): string {
  const lines = [
    `Hi Team,`,
    ``,
    `Following up on our meetings:`,
    `- ${comparison.meeting_a.title} (${formatDate(comparison.meeting_a.date)})`,
    `- ${comparison.meeting_b.title} (${formatDate(comparison.meeting_b.date)})`,
    ``,
    `Key updates since our last meeting:`,
    ``,
  ];

  if (comparison.commitments.new_commitments.length > 0) {
    lines.push(`New Commitments:`);
    comparison.commitments.new_commitments.forEach((c) => {
      lines.push(`- ${c.task}${c.owner ? ` (Owner: ${c.owner})` : ""}${c.deadline ? ` - Due: ${c.deadline}` : ""}`);
    });
    lines.push(``);
  }

  if (comparison.commitments.changed_deadlines.length > 0) {
    lines.push(`Deadline Changes:`);
    comparison.commitments.changed_deadlines.forEach((c) => {
      lines.push(`- ${c.task}: ${c.meeting_a_deadline || c.meeting_a_deadline_text || "Not set"} → ${c.meeting_b_deadline || c.meeting_b_deadline_text || "Not set"}`);
    });
    lines.push(``);
  }

  if (comparison.commitments.changed_ownership.length > 0) {
    lines.push(`Ownership Changes:`);
    comparison.commitments.changed_ownership.forEach((c) => {
      lines.push(`- ${c.task}: ${c.meeting_a_owner || "Unassigned"} → ${c.meeting_b_owner || "Unassigned"}`);
    });
    lines.push(``);
  }

  if (comparison.decisions.new_decisions.length > 0) {
    lines.push(`New Decisions:`);
    comparison.decisions.new_decisions.forEach((d) => {
      lines.push(`- ${d.title}: ${d.description}`);
    });
    lines.push(``);
  }

  lines.push(
    `Please review and let me know if any corrections are needed.`,
    ``,
    `Best regards`,
  );

  return lines.join("\n");
}