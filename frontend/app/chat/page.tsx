"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";

const API =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type ChatSource = {
  source_number: number;
  meeting_id: string;
  content: string;
  similarity: number;
};

type Message = {
  id: number;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
};

function MeetingChatContent() {
  const searchParams = useSearchParams();
  const meetingId = searchParams.get("meeting_id");

  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

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

    try {
      const response = await fetch(`${API}/api/chat/ask`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: text,
          meeting_id: meetingId || undefined,
          limit: 5,
          similarity_threshold: 0.6,
        }),
      });

      if (!response.ok) {
        throw new Error(
          `AI Meeting Chat failed (${response.status})`
        );
      }

      const data: {
        answer: string;
        sources: ChatSource[];
      } = await response.json();

      setMessages((previous) => [
        ...previous,
        {
          id: id + 1,
          role: "assistant",
          content: data.answer,
          sources: data.sources,
        },
      ]);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to generate an answer."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main
      style={{
        maxWidth: 900,
        margin: "0 auto",
        padding: "32px 24px",
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <Link href={meetingId ? `/meetings/${meetingId}` : "/"}>
        {meetingId ? "← Back to Meeting" : "← Back to Dashboard"}
      </Link>

      <header style={{ marginTop: 28, marginBottom: 24 }}>
        <h1>
          {meetingId ? "Ask AI About This Meeting" : "AI Meeting Chat"}
        </h1>
        <p style={{ opacity: 0.7 }}>
          {meetingId
            ? "Answers are based only on evidence indexed for this meeting."
            : "Ask questions across all indexed meetings."}
        </p>
      </header>

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
            <p>
              Try asking: Who is responsible for the
              assigned tasks?
            </p>
          </div>
        )}

        {messages.map((message) => (
          <article
            key={message.id}
            style={{
              alignSelf:
                message.role === "user"
                  ? "flex-end"
                  : "stretch",
              maxWidth:
                message.role === "user" ? "80%" : "100%",
              background:
                message.role === "user"
                  ? "#252525"
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
            </div>

            {message.role === "assistant" &&
              message.sources &&
              message.sources.length > 0 && (
                <div style={{ marginTop: 20 }}>
                  <h3>Meeting Sources</h3>

                  {message.sources.map((source) => (
                    <div
                      key={source.source_number}
                      style={{
                        border: "1px solid #7775",
                        borderRadius: 10,
                        padding: 14,
                        marginTop: 12,
                      }}
                    >
                      <Link
                        href={`/meetings/${source.meeting_id}`}
                      >
                        [{source.source_number}] View Meeting
                      </Link>

                      <p
                        style={{
                          marginTop: 10,
                          lineHeight: 1.6,
                          whiteSpace: "pre-wrap",
                        }}
                      >
                        {source.content}
                      </p>

                      <small style={{ opacity: 0.7 }}>
                        Similarity:{" "}
                        {Math.round(
                          source.similarity * 100
                        )}
                        %
                      </small>
                    </div>
                  ))}
                </div>
              )}
          </article>
        ))}

        {loading && (
          <p role="status" style={{ opacity: 0.7 }}>
            Searching meeting evidence and generating an answer...
          </p>
        )}
      </section>

      {error && (
        <p role="alert" style={{ color: "#dc5555" }}>
          {error}
        </p>
      )}

      <form
        onSubmit={handleSubmit}
        style={{
          display: "flex",
          gap: 12,
          padding: "16px 0",
          borderTop: "1px solid #7775",
        }}
      >
        <input
          type="text"
          aria-label="Ask about your meetings"
          value={question}
          onChange={(event) =>
            setQuestion(event.target.value)
          }
          placeholder="Ask anything about your meetings..."
          maxLength={2000}
          disabled={loading}
          required
          style={{
            flex: 1,
            minWidth: 0,
            padding: 14,
            borderRadius: 10,
            border: "1px solid #888",
            background: "transparent",
            color: "inherit",
          }}
        />

        <button
          type="submit"
          disabled={loading || !question.trim()}
          style={{
            padding: "12px 22px",
            borderRadius: 10,
            background: "#252525",
            color: "#ffffff",
            cursor: loading ? "wait" : "pointer",
          }}
        >
          {loading ? "Thinking..." : "Send"}
        </button>
      </form>
    </main>
  );
}

export default function MeetingChatPage() {
  return (
    <Suspense fallback={<main style={{ padding: 32 }}>Loading meeting chat...</main>}>
      <MeetingChatContent />
    </Suspense>
  );
}
