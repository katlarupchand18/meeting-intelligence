"use client";

import {
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type DragEvent,
} from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const MEETING_TYPES = [
  { value: "business", label: "Business" },
  { value: "team", label: "Team Meeting" },
  { value: "client", label: "Client Meeting" },
  { value: "academic", label: "Academic" },
  { value: "political", label: "Political" },
  { value: "interview", label: "Interview" },
  { value: "personal", label: "Personal" },
  { value: "other", label: "Other" },
];

const ACCEPTED_EXTENSIONS = [
  ".mp3",
  ".wav",
  ".m4a",
  ".aac",
  ".flac",
  ".ogg",
  ".webm",
  ".mp4",
  ".mov",
  ".avi",
  ".mkv",
];

function getErrorMessage(detail: unknown, status: number): string {
  if (typeof detail === "string" && detail.trim()) {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail.map((item: unknown) => {
      if (typeof item === "string") return item;

      if (item && typeof item === "object") {
        const error = item as {
          loc?: unknown[];
          msg?: unknown;
          message?: unknown;
        };

        const location = Array.isArray(error.loc)
          ? error.loc
              .filter((part) => part !== undefined && part !== null)
              .join(" → ")
          : "";

        const description =
          typeof error.msg === "string"
            ? error.msg
            : typeof error.message === "string"
              ? error.message
              : JSON.stringify(item);

        return location ? `${location}: ${description}` : description;
      }

      return String(item);
    });

    if (messages.length > 0) {
      return messages.join("; ");
    }
  }

  if (detail && typeof detail === "object") {
    const error = detail as {
      message?: unknown;
      detail?: unknown;
    };

    if (typeof error.message === "string") {
      return error.message;
    }

    if (typeof error.detail === "string") {
      return error.detail;
    }

    return JSON.stringify(detail);
  }

  return `Failed to create meeting (HTTP ${status}).`;
}

export default function NewMeetingPage() {
  const router = useRouter();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [meetingType, setMeetingType] = useState("business");
  const [file, setFile] = useState<File | null>(null);

  const [inputMode, setInputMode] = useState<"recording" | "file" | "paste">("recording");
  const [transcriptFile, setTranscriptFile] = useState<File | null>(null);
  const [transcriptText, setTranscriptText] = useState("");
  const [dragging, setDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  function validateFile(selectedFile: File): boolean {
    const extension = `.${selectedFile.name.split(".").pop()?.toLowerCase()}`;

    if (!ACCEPTED_EXTENSIONS.includes(extension)) {
      setError(
        "Unsupported file format. Please select a supported audio or video recording."
      );
      return false;
    }

    if (selectedFile.size === 0) {
      setError("The selected file is empty. Please choose another file.");
      return false;
    }

    setFile(selectedFile);
    setError("");
    setSuccess("");
    setProgress(0);

    return true;
  }

  function validateTranscriptFile(selectedFile: File): boolean {
    if (!selectedFile.name.toLowerCase().endsWith(".txt")) {
      setError("Only .txt transcript files are supported.");
      return false;
    }

    if (selectedFile.size === 0 || selectedFile.size > 2 * 1024 * 1024) {
      setError("Transcript must be non-empty and no larger than 2 MB.");
      return false;
    }

    setTranscriptFile(selectedFile);
    setError("");
    setSuccess("");
    return true;
  }

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];

    if (selectedFile) {
      validateFile(selectedFile);
    }

    // Allow the same file to be selected again.
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);

    if (loading) return;

    const droppedFile = event.dataTransfer.files?.[0];

    if (droppedFile) {
      validateFile(droppedFile);
    }
  }

  function formatFileSize(bytes: number): string {
    if (bytes < 1024) {
      return `${bytes} B`;
    }

    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }

    if (bytes < 1024 * 1024 * 1024) {
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
  }

  async function createMeeting(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!title.trim()) {
      setError("Please enter a meeting title.");
      return;
    }

    if (inputMode === "recording" && !file) {
      setError("Please select an audio or video recording.");
      return;
    }

    if (inputMode === "file" && !transcriptFile) {
      setError("Please select a .txt transcript file.");
      return;
    }

    if (inputMode === "paste" && !transcriptText.trim()) {
      setError("Please paste your meeting transcript.");
      return;
    }

    if (
      inputMode === "paste" &&
      new TextEncoder().encode(transcriptText.trim()).length > 2 * 1024 * 1024
    ) {
      setError("Transcript exceeds 2 MB.");
      return;
    }

    setLoading(true);
    setProgress(0);

    try {
      const formData = new FormData();

      formData.append("title", title.trim());
      formData.append("description", description.trim());
      formData.append("meeting_type", meetingType);
      if (inputMode === "recording" && file) {
        formData.append("file", file);
      } else if (inputMode === "file" && transcriptFile) {
        formData.append("file", transcriptFile);
      } else if (inputMode === "paste") {
        formData.append("transcript_text", transcriptText.trim());
      }

      const endpoint =
        inputMode === "recording"
          ? `${API_URL}/api/meetings`
          : `${API_URL}/api/meetings/from-transcript`;

      const response = await fetch(endpoint, {
        method: "POST",
        body: formData,
      });

      const responseText = await response.text();

      let data: any = {};

      try {
        data = responseText ? JSON.parse(responseText) : {};
      } catch {
        data = { detail: responseText };
      }

      if (!response.ok) {
        throw new Error(
          getErrorMessage(data?.detail ?? data?.message, response.status)
        );
      }

      setProgress(100);
      setSuccess("Meeting created successfully.");

      const meetingId =
        data?.id ?? data?.data?.id ?? data?.meeting?.id;

      if (meetingId) {
        router.push(`/meetings/${meetingId}`);
      } else {
        router.push("/");
      }
    } catch (err) {
      if (err instanceof TypeError) {
        setError(
          "Could not connect to the backend. Check that the backend is running at http://127.0.0.1:8000."
        );
      } else {
        setError(
          err instanceof Error
            ? err.message
            : "Something went wrong while creating the meeting."
        );
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-wrapper">
      <Link href="/" className="back-link">
        ← Dashboard
      </Link>

      <h1>Add a Meeting Recording</h1>

      <p className="text-slate-500">
        Upload a meeting recording to extract the conversation, speakers,
        decisions, commitments, evidence, and accountability information.
      </p>

      <form onSubmit={createMeeting} style={{ marginTop: 24, display: "flex", flexDirection: "column", gap: 24 }}>
        {/* Meeting information */}
        <section className="meeting-card">
          <div className="meeting-card-heading">
            <div>
              <span className="eyebrow">MEETING INFO</span>
              <h2>Meeting Information</h2>
            </div>
          </div>
          <div style={{ marginTop: 16, display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
            <div style={{ gridColumn: "1 / -1" }}>
              <label
                htmlFor="meeting-title"
                style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 6, color: "#374151" }}
              >
                Meeting title <span style={{ color: "#ef4444" }}> *</span>
              </label>

              <input
                id="meeting-title"
                type="text"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="e.g. Project Review Meeting"
                maxLength={200}
                required
                disabled={loading}
                className="meeting-search"
                style={{ fontSize: 16 }}
              />
            </div>

            <div>
              <label
                htmlFor="meeting-type"
                style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 6, color: "#374151" }}
              >
                Meeting type
              </label>

              <select
                id="meeting-type"
                value={meetingType}
                onChange={(event) => setMeetingType(event.target.value)}
                disabled={loading}
                className="meeting-search"
                style={{ fontSize: 16 }}
              >
                {MEETING_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label
                htmlFor="meeting-description"
                style={{ display: "block", fontSize: 14, fontWeight: 500, marginBottom: 6, color: "#374151" }}
              >
                Description
              </label>

              <input
                id="meeting-description"
                type="text"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                placeholder="Optional description"
                maxLength={2000}
                disabled={loading}
                className="meeting-search"
                style={{ fontSize: 16 }}
              />
            </div>
          </div>
        </section>

        {/* Input method selector */}
        <section className="meeting-card">
          <div className="meeting-card-heading">
            <div>
              <span className="eyebrow">INPUT METHOD</span>
              <h2>Choose Input Method</h2>
            </div>
          </div>
          <div style={{ marginTop: 16, display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))" }}>
            {([
              ["recording", "🎙️ Audio / Video"],
              ["file", "📄 Transcript File"],
              ["paste", "✍️ Paste Transcript"],
            ] as const).map(([mode, label]) => (
              <button
                key={mode}
                type="button"
                disabled={loading}
                onClick={() => {
                  setInputMode(mode);
                  setError("");
                  setSuccess("");
                }}
                style={{
                  padding: "16px 20px",
                  borderRadius: 12,
                  border: "2px solid",
                  fontSize: 15,
                  fontWeight: 500,
                  cursor: loading ? "not-allowed" : "pointer",
                  background: inputMode === mode ? "#eff6ff" : "#fff",
                  color: inputMode === mode ? "#1d4ed8" : "#475569",
                  borderColor: inputMode === mode ? "#3b82f6" : "#e2e8f0",
                  transition: "all 0.2s",
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </section>

        {inputMode === "recording" && (
          <section className="meeting-card">
            <div className="meeting-card-heading">
              <div>
                <span className="eyebrow">RECORDING</span>
                <h2>Upload Recording</h2>
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: 14, color: "#64748b", marginBottom: 16 }}>
                Select an audio or video file from your computer.
              </p>

              <label
                onDragOver={(event) => {
                  event.preventDefault();
                  if (!loading) setDragging(true);
                }}
                onDragLeave={(event) => {
                  event.preventDefault();
                  setDragging(false);
                }}
                onDrop={handleDrop}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  minHeight: 250,
                  borderRadius: 16,
                  border: "2px dashed",
                  padding: 32,
                  textAlign: "center",
                  cursor: loading ? "not-allowed" : "pointer",
                  borderColor: dragging ? "#3b82f6" : loading ? "#cbd5e1" : "#94a3b8",
                  background: dragging ? "#eff6ff" : loading ? "#f8fafc" : "#fafafa",
                  transition: "all 0.2s",
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={ACCEPTED_EXTENSIONS.join(",")}
                  onChange={handleFileChange}
                  disabled={loading}
                  className="hidden"
                />

                <div style={{ marginBottom: 16, width: 64, height: 64, borderRadius: 16, background: "#dbeafe", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 32 }}>
                  🎙️
                </div>

                {file ? (
                  <>
                    <p style={{ wordBreak: "break-all", fontWeight: 500, color: "#1e293b" }}>
                      {file.name}
                    </p>

                    <p style={{ marginTop: 8, fontSize: 14, color: "#64748b" }}>
                      {formatFileSize(file.size)}
                    </p>

                    <span style={{ marginTop: 16, display: "inline-block", padding: "8px 16px", borderRadius: 8, background: "#f1f5f9", fontSize: 13, color: "#64748b" }}>
                      {loading ? "Uploading file..." : "Click to choose another file"}
                    </span>
                  </>
                ) : (
                  <>
                    <p style={{ fontWeight: 500, color: "#1e293b" }}>
                      Drop your recording here
                    </p>

                    <p style={{ marginTop: 8, fontSize: 14, color: "#64748b" }}>
                      or click to browse your computer
                    </p>

                    <span style={{ marginTop: 16, display: "inline-block", fontSize: 12, color: "#94a3b8" }}>
                      MP3 · WAV · M4A · AAC · FLAC · OGG · MP4 · MOV · WEBM · AVI · MKV
                    </span>
                  </>
                )}
              </label>

              {loading && (
                <div style={{ marginTop: 20 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14, marginBottom: 8 }}>
                    <span style={{ color: "#64748b" }}>Sending recording...</span>
                    <span style={{ color: "#3b82f6" }}>
                      {progress === 100 ? "Complete" : "Please wait"}
                    </span>
                  </div>

                  <div style={{ height: 8, borderRadius: 9999, background: "#e2e8f0", overflow: "hidden" }}>
                    <div
                      style={{
                        height: "100%",
                        borderRadius: 9999,
                        background: "linear-gradient(90deg, #3b82f6, #2563eb)",
                        width: progress === 100 ? "100%" : "33%",
                        transition: "width 0.3s",
                      }}
                    />
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {inputMode === "file" && (
          <section className="meeting-card">
            <div className="meeting-card-heading">
              <div>
                <span className="eyebrow">TRANSCRIPT FILE</span>
                <h2>Upload Transcript</h2>
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: 14, color: "#64748b", marginBottom: 16 }}>
                UTF-8 .txt files only, maximum 2 MB.
              </p>

              <input
                type="file"
                accept=".txt,text/plain"
                disabled={loading}
                onChange={(event) => {
                  const selected = event.target.files?.[0];
                  if (selected) validateTranscriptFile(selected);
                  event.target.value = "";
                }}
                className="meeting-search"
                style={{ padding: 16 }}
              />

              {transcriptFile && (
                <p style={{ marginTop: 12, fontSize: 14, color: "#2563eb" }}>
                  Selected: {transcriptFile.name} ({formatFileSize(transcriptFile.size)})
                </p>
              )}
            </div>
          </section>
        )}

        {inputMode === "paste" && (
          <section className="meeting-card">
            <div className="meeting-card-heading">
              <div>
                <span className="eyebrow">PASTE TRANSCRIPT</span>
                <h2>Paste Transcript</h2>
              </div>
            </div>
            <div style={{ marginTop: 16 }}>
              <p style={{ fontSize: 14, color: "#64748b", marginBottom: 16 }}>
                Paste the conversation from your meeting.
              </p>

              <textarea
                value={transcriptText}
                onChange={(event) => setTranscriptText(event.target.value)}
                disabled={loading}
                rows={12}
                placeholder="[00:00] Alice: Let's review the project.\n[00:15] Bob: I'll finish the report by Friday."
                className="meeting-search"
                style={{ fontFamily: "monospace", fontSize: 14, minHeight: 200 }}
              />

              <p style={{ marginTop: 8, fontSize: 12, color: "#94a3b8" }}>
                {new TextEncoder().encode(transcriptText).length.toLocaleString()} / 2,097,152 bytes
              </p>
            </div>
          </section>
        )}

        {/* Error message */}
        {error && (
          <p role="alert" className="meeting-alert meeting-alert-error">
            <strong>Unable to create meeting</strong>
            <p style={{ marginTop: 4 }}>{error}</p>
          </p>
        )}

        {/* Success message */}
        {success && (
          <p role="status" className="meeting-alert meeting-alert-success">
            {success}
          </p>
        )}

        {/* Actions */}
        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
          <button
            type="button"
            onClick={() => router.push("/")}
            disabled={loading}
            style={{
              padding: "12px 20px",
              borderRadius: 12,
              border: "1px solid #cbd5e1",
              background: "#fff",
              color: "#374151",
              fontSize: 14,
              fontWeight: 500,
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.5 : 1,
            }}
          >
            Cancel
          </button>

          <button
            type="submit"
            disabled={
              loading ||
              !title.trim() ||
              (inputMode === "recording" && !file) ||
              (inputMode === "file" && !transcriptFile) ||
              (inputMode === "paste" && !transcriptText.trim())
            }
            className="primary-button"
            style={{ padding: "12px 24px", fontSize: 14, fontWeight: 600 }}
          >
            {loading ? "Uploading..." : "Create Meeting →"}
          </button>
        </div>
      </form>
    </main>
  );
}