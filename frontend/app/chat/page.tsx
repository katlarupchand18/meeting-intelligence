"use client";

import { FormEvent, useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";

const API =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type ChatSource = {
  source_number: number;
  meeting_id: string | null;
  content: string;
  similarity: number;
  type: string;
  retrieval_method: string;
  metadata: Record<string, unknown>;
};

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  streaming?: boolean;
  intent?: string;
  provider?: string;
  note?: string;
};

type StreamEvent = {
  type: string;
  content?: string;
  question?: string;
  answer?: string;
  sources?: ChatSource[];
  error?: string;
  intent?: string;
  provider?: string;
  note?: string;
};

type ConversationHistory = {
  session_id: string;
  turns: Array<{
    role: string;
    content: string;
    timestamp: string;
    metadata: Record<string, unknown>;
  }>;
  current_meeting_id: string | null;
};

function MeetingChatContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const meetingId = searchParams.get("meeting_id");

  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [useFastModel, setUseFastModel] = useState(true);
  const [showHistory, setShowHistory] = useState(false);
  const [sessionId, setSessionId] = useState<string>(() => {
    // Generate or retrieve session ID from localStorage
    if (typeof window !== "undefined") {
      let sid = localStorage.getItem("chat_session_id");
      if (!sid) {
        sid = crypto.randomUUID();
        localStorage.setItem("chat_session_id", sid);
      }
      return sid;
    }
    return crypto.randomUUID();
  });
  const eventSourceRef = useRef<EventSource | null>(null);

  const cleanupEventSource = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  // Initialize session on mount
  useEffect(() => {
    if (typeof window !== "undefined") {
      let sid = localStorage.getItem("chat_session_id");
      if (!sid) {
        sid = crypto.randomUUID();
        localStorage.setItem("chat_session_id", sid);
      }
      setSessionId(sid);
    }
  }, []);

  // Handle new chat
  const handleNewChat = async () => {
    try {
      const response = await fetch(`${API}/api/chat/new`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      const data = await response.json();
      if (data.session_id) {
        localStorage.setItem("chat_session_id", data.session_id);
        setSessionId(data.session_id);
        setMessages([]);
        setError("");
      }
    } catch (err) {
      console.error("Failed to start new chat:", err);
      // Fallback: just clear locally
      setMessages([]);
      const newSid = crypto.randomUUID();
      localStorage.setItem("chat_session_id", newSid);
      setSessionId(newSid);
    }
  };

  // Load conversation history
  const loadHistory = async () => {
    try {
      const response = await fetch(`${API}/api/chat/history/${sessionId}`);
      const data: ConversationHistory = await response.json();

      // Convert history to messages
      const historyMessages: Message[] = [];
      for (let i = 0; i < data.turns.length; i++) {
        const turn = data.turns[i];
        historyMessages.push({
          id: Date.now() + i,
          role: turn.role as "user" | "assistant",
          content: turn.content,
          streaming: false,
        });
      }
      setMessages(historyMessages);
      setShowHistory(false);
    } catch (err) {
      console.error("Failed to load history:", err);
    }
  };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const text = question.trim();

    if (!text || loading) return;

    const id = Date.now();

    setMessages((previous) => [
      ...previous,
      { id, role: "user", content: text },
    ]);

    setQuestion("");
    setLoading(true);
    setError("");

    // Add a placeholder for the streaming assistant message
    const assistantId = id + 1;
    setMessages((previous) => [
      ...previous,
      { id: assistantId, role: "assistant", content: "", streaming: true },
    ]);

    try {
      const response = await fetch(`${API}/api/chat/ask/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: text,
          meeting_id: meetingId || undefined,
          limit: 10,
          similarity_threshold: 0.35,
          use_fast_model: useFastModel,
          session_id: sessionId,
        }),
      });

      if (!response.ok) {
        throw new Error(
          `AI Meeting Chat failed (${response.status})`
        );
      }

      // Process Server-Sent Events
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }

      const decoder = new TextDecoder();
      let buffer = "";
      let fullAnswer = "";
      let sources: ChatSource[] = [];
      let intent = "";
      let provider = "";
      let note = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const eventData = JSON.parse(line.slice(6)) as StreamEvent;

              switch (eventData.type) {
                case "sources":
                  if (eventData.sources) {
                    sources = eventData.sources;
                  }
                  break;

                case "content":
                  if (eventData.content) {
                    fullAnswer += eventData.content;
                    setMessages((prev) =>
                      prev.map((msg) =>
                        msg.id === assistantId
                          ? { ...msg, content: fullAnswer }
                          : msg
                      )
                    );
                  }
                  break;

                case "done":
                  if (eventData.answer) {
                    fullAnswer = eventData.answer;
                  }
                  if (eventData.sources) {
                    sources = eventData.sources;
                  }
                  intent = eventData.intent || "";
                  provider = eventData.provider || "";
                  note = eventData.note || "";

                  setMessages((prev) =>
                    prev.map((msg) =>
                      msg.id === assistantId
                        ? {
                            ...msg,
                            content: fullAnswer,
                            streaming: false,
                            sources,
                            intent,
                            provider,
                            note,
                          }
                        : msg
                    )
                  );
                  break;

                case "error":
                  setError(eventData.error || "An error occurred");
                  setMessages((prev) =>
                    prev.filter((msg) => msg.id !== assistantId)
                  );
                  break;
              }
            } catch (e) {
              // Ignore parse errors for incomplete chunks
            }
          }
        }
      }
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to generate an answer."
      );
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantId));
    } finally {
      setLoading(false);
      cleanupEventSource();
    }
  }

  // Format timestamp for display
  const formatTime = (timestamp: number) => {
    return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Format source for display
  const formatSource = (source: ChatSource) => {
    const methodLabels: Record<string, string> = {
      structured: "📊 Structured",
      semantic: "🔍 Semantic",
      keyword: "📝 Keyword",
      person_name: "👤 Person",
      transcript_keyword: "📝 Transcript",
      person_transcript: "👤 Mention",
    };
    return methodLabels[source.retrieval_method] || source.retrieval_method;
  };

  return (
    <main className="page-wrapper" style={{ minHeight: "calc(100vh - 200px)", display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
        <Link href={meetingId ? `/meetings/${meetingId}` : "/"} className="back-link">
          {meetingId ? "← Back to Meeting" : "← Back to Dashboard"}
        </Link>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <button
            onClick={handleNewChat}
            disabled={loading}
            className="primary-button"
            style={{ fontSize: 13, padding: "8px 16px" }}
            title="Start a new conversation (clears history)"
          >
            + New Chat
          </button>
          <button
            onClick={() => setShowHistory(!showHistory)}
            disabled={loading}
            className="primary-button"
            style={{ fontSize: 13, padding: "8px 16px", background: showHistory ? "#1e293b" : "var(--primary)" }}
          >
            {showHistory ? "Hide History" : "Show History"}
          </button>
        </div>
      </div>

      <header style={{ marginTop: 8, marginBottom: 24 }}>
        <h1>
          {meetingId ? "Ask AI About This Meeting" : "AI Meeting Chat"}
        </h1>
        <p className="text-slate-500">
          {meetingId
            ? "Answers are based on evidence indexed for this meeting."
            : "Ask questions across all indexed meetings. Try greetings, general questions, or meeting-specific queries."}
        </p>
        <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, fontSize: 14 }}>
          <input
            type="checkbox"
            checked={useFastModel}
            onChange={(e) => setUseFastModel(e.target.checked)}
            disabled={loading}
          />
          <span>Use fast model (Llama 3.2 3B) for quicker responses</span>
        </label>
      </header>

      {showHistory && (
        <section style={{ marginBottom: 24, padding: 16, background: "#f8fafc", borderRadius: 8 }}>
          <h3 style={{ marginBottom: 12 }}>Conversation History</h3>
          <button
            onClick={loadHistory}
            disabled={loading}
            className="primary-button"
            style={{ fontSize: 13, padding: "6px 12px", marginBottom: 12 }}
          >
            Load Full History
          </button>
          <p style={{ fontSize: 13, color: "#64748b" }}>
            Session: <code>{sessionId.slice(0, 8)}...</code>
            {meetingId && <span style={{ marginLeft: 12 }}> | Meeting: <code>{meetingId.slice(0, 8)}...</code></span>}
          </p>
        </section>
      )}

      <section
        aria-label="Chat conversation"
        aria-live="polite"
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          gap: 20,
          paddingBottom: 32,
        }}
      >
        {messages.length === 0 && (
          <div
            style={{
              textAlign: "center",
              padding: "64px 20px",
              opacity: 0.75,
            }}
          >
            <h2>What would you like to know?</h2>
            <p style={{ marginTop: 8, lineHeight: 1.8 }}>
              <strong>Meeting questions:</strong> "What commitments were made?", "Who is responsible for the auth bug?",
              "When is the deadline?", "Summarize the decisions."
            </p>
            <p style={{ marginTop: 8, lineHeight: 1.8 }}>
              <strong>General questions:</strong> "How does RAG work?", "What is a commitment?", "Explain semantic search."
            </p>
            <p style={{ marginTop: 8, lineHeight: 1.8 }}>
              <strong>Greetings:</strong> "Hello", "Hi there", "Good morning"
            </p>
          </div>
        )}

        {messages.map((message) => (
          <article
            key={message.id}
            className="meeting-card"
            style={{
              alignSelf:
                message.role === "user"
                  ? "flex-end"
                  : "stretch",
              maxWidth:
                message.role === "user" ? "80%" : "100%",
              background:
                message.role === "user"
                  ? "#1e293b"
                  : "transparent",
              color:
                message.role === "user"
                  ? "#ffffff"
                  : "inherit",
              padding:
                message.role === "user"
                  ? "14px 18px"
                  : "8px 0",
              borderRadius: 14,
              opacity: message.streaming ? 0.9 : 1,
            }}
          >
            <div
              style={{
                whiteSpace: "pre-wrap",
                lineHeight: 1.7,
                overflowWrap: "anywhere",
              }}
            >
              {message.content}
              {message.streaming && <span style={{ animation: "blink 1s infinite" }}>▌</span>}
            </div>

            {/* Intent/Provider badges */}
            {(message.intent || message.provider) && (
              <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap" }}>
                {message.intent && (
                  <span
                    style={{
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 12,
                      background: "rgba(99, 102, 241, 0.15)",
                      color: "#6366f1",
                      fontWeight: 500,
                      textTransform: "capitalize",
                    }}
                  >
                    {message.intent.replace(/_/g, " ")}
                  </span>
                )}
                {message.provider && (
                  <span
                    style={{
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 12,
                      background: "rgba(16, 185, 129, 0.15)",
                      color: "#10b981",
                      fontWeight: 500,
                    }}
                  >
                    {message.provider}
                  </span>
                )}
                {message.note && (
                  <span
                    style={{
                      fontSize: 11,
                      padding: "2px 8px",
                      borderRadius: 12,
                      background: "rgba(245, 158, 11, 0.15)",
                      color: "#f59e0b",
                      fontWeight: 500,
                    }}
                  >
                    {message.note}
                  </span>
                )}
              </div>
            )}

            {message.role === "assistant" &&
              message.sources &&
              message.sources.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Meeting Sources ({message.sources.length})</h3>

                  {message.sources.map((source) => (
                    <div
                      key={source.source_number}
                      className="meeting-card"
                      style={{ marginTop: 12, padding: 16 }}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                        {source.meeting_id && (
                          <Link
                            href={`/meetings/${source.meeting_id}`}
                            className="primary-button"
                            style={{ fontSize: 12, padding: "4px 10px" }}
                          >
                            [{source.source_number}] View Meeting →
                          </Link>
                        )}
                        <span
                          style={{
                            fontSize: 11,
                            padding: "2px 6px",
                            borderRadius: 4,
                            background: "#e2e8f0",
                            color: "#475569",
                          }}
                        >
                          {formatSource(source)}
                        </span>
                      </div>

                      <p
                        style={{
                          marginTop: 10,
                          lineHeight: 1.6,
                          whiteSpace: "pre-wrap",
                          fontSize: 14,
                        }}
                      >
                        {source.content}
                      </p>

                      <div style={{ display: "flex", gap: 16, marginTop: 8, flexWrap: "wrap" }}>
                        <small style={{ opacity: 0.7, fontSize: 11 }}>
                          Similarity: {Math.round(source.similarity * 100)}%
                        </small>
                        {source.metadata && Object.keys(source.metadata).length > 0 && (
                          <small style={{ opacity: 0.7, fontSize: 11 }}>
                            {JSON.stringify(source.metadata).slice(0, 100)}...
                          </small>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
          </article>
        ))}

        {loading && (
          <p role="status" className="text-slate-500">
            Searching meeting evidence and generating an answer...
          </p>
        )}
      </section>

      {error && (
        <p role="alert" className="meeting-alert meeting-alert-error" style={{ marginTop: 16 }}>
          {error}
        </p>
      )}

      <form
        onSubmit={handleSubmit}
        style={{
          display: "flex",
          gap: 12,
          padding: "16px 0",
          borderTop: "1px solid #e2e8f0",
          marginTop: "auto",
        }}
      >
        <input
          type="text"
          aria-label="Ask about your meetings"
          value={question}
          onChange={(event) =>
            setQuestion(event.target.value)
          }
          placeholder="Ask anything about your meetings... (try 'Hello', 'What commitments?', 'Who owns auth bug?')"
          maxLength={2000}
          disabled={loading}
          required
          className="meeting-search"
          style={{ flex: 1, minWidth: 0, padding: 14 }}
        />

        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="primary-button"
        >
          {loading ? "Thinking..." : "Send"}
        </button>
      </form>

      <style jsx>{`
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </main>
  );
}

export default function MeetingChatPage() {
  return (
    <Suspense fallback={<main className="page-wrapper" style={{ padding: 32 }}>Loading meeting chat...</main>}>
      <MeetingChatContent />
    </Suspense>
  );
}