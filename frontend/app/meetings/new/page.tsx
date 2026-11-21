"use client";

import {
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
  type DragEvent,
} from "react";
import { useRouter } from "next/navigation";

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
    <main className="upload-page-redesigned">
      {/* Page content */}
      <section className="upload-content-redesigned">
        <div className="mb-8">
          <div className="mb-3 inline-flex rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-semibold text-blue-700">
            New Meeting
          </div>

          <h2 className="text-3xl font-bold tracking-tight">
            Add a meeting recording
          </h2>

          <p className="mt-2 text-slate-500">
            Upload a meeting recording to extract the conversation, speakers,
            decisions, commitments, evidence, and accountability information.
          </p>
        </div>

        <form onSubmit={createMeeting} className="space-y-6">
          {/* Meeting information */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-5 text-lg font-semibold">
              Meeting information
            </h3>

            <div className="grid gap-5 md:grid-cols-2">
              <div className="md:col-span-2">
                <label
                  htmlFor="meeting-title"
                  className="mb-2 block text-sm font-medium text-slate-700"
                >
                  Meeting title <span className="text-red-400">*</span>
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
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-blue-500/60 disabled:opacity-60"
                />
              </div>

              <div>
                <label
                  htmlFor="meeting-type"
                  className="mb-2 block text-sm font-medium text-slate-700"
                >
                  Meeting type
                </label>

                <select
                  id="meeting-type"
                  value={meetingType}
                  onChange={(event) => setMeetingType(event.target.value)}
                  disabled={loading}
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-blue-500/60 disabled:opacity-60"
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
                  className="mb-2 block text-sm font-medium text-slate-700"
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
                  className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-blue-500/60 disabled:opacity-60"
                />
              </div>
            </div>
          </div>

          
            {/* Input method selector */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-lg font-semibold">
                Choose input method
              </h3>

              <div className="grid gap-3 sm:grid-cols-3">
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
                    className={`rounded-xl border px-4 py-4 text-sm font-medium transition ${
                      inputMode === mode
                        ? "border-blue-500 bg-blue-50 text-blue-700"
                        : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {inputMode === "recording" && (
              <>

          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <h3 className="mb-2 text-lg font-semibold">Recording</h3>

            <p className="mb-5 text-sm text-slate-500">
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
              className={`flex min-h-[250px] flex-col items-center justify-center rounded-2xl border border-dashed p-8 text-center transition ${
                loading ? "cursor-not-allowed opacity-60" : "cursor-pointer"
              } ${
                dragging
                  ? "border-blue-500 bg-blue-50"
                  : "border-blue-200 bg-blue-50/40 hover:border-blue-400 hover:bg-blue-50"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept={ACCEPTED_EXTENSIONS.join(",")}
                onChange={handleFileChange}
                disabled={loading}
                className="hidden"
              />

              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-500/10 text-3xl">
                🎙️
              </div>

              {file ? (
                <>
                  <p className="break-all font-medium text-slate-800">
                    {file.name}
                  </p>

                  <p className="mt-2 text-sm text-slate-500">
                    {formatFileSize(file.size)}
                  </p>

                  <span className="mt-4 rounded-lg bg-slate-100 px-4 py-2 text-xs text-slate-500">
                    {loading
                      ? "Uploading file..."
                      : "Click to choose another file"}
                  </span>
                </>
              ) : (
                <>
                  <p className="font-medium text-slate-800">
                    Drop your recording here
                  </p>

                  <p className="mt-2 text-sm text-slate-500">
                    or click to browse your computer
                  </p>

                  <span className="mt-4 text-xs text-slate-400">
                    MP3 · WAV · M4A · AAC · FLAC · OGG · MP4 · MOV · WEBM · AVI
                    · MKV
                  </span>
                </>
              )}
            </label>

            {loading && (
              <div className="mt-5">
                <div className="mb-2 flex justify-between text-sm">
                  <span className="text-slate-500">Sending recording...</span>
                  <span className="text-blue-300">
                    {progress === 100 ? "Complete" : "Please wait"}
                  </span>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-slate-200">
                  <div
                    className={`h-full rounded-full bg-gradient-to-r from-blue-500 to-blue-600 ${
                      progress === 100
                        ? "w-full"
                        : "w-1/3 animate-pulse"
                    }`}
                  />
                </div>
              </div>
            )}
          </div>

          
              </>
            )}

            {inputMode === "file" && (
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="mb-2 text-lg font-semibold">
                  Upload transcript
                </h3>
                <p className="mb-4 text-sm text-slate-500">
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
                  className="block w-full rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-700"
                />

                {transcriptFile && (
                  <p className="mt-3 text-sm text-blue-700">
                    Selected: {transcriptFile.name} ({formatFileSize(transcriptFile.size)})
                  </p>
                )}
              </div>
            )}

            {inputMode === "paste" && (
              <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="mb-2 text-lg font-semibold">
                  Paste transcript
                </h3>
                <p className="mb-4 text-sm text-slate-500">
                  Paste the conversation from your meeting.
                </p>

                <textarea
                  value={transcriptText}
                  onChange={(event) => setTranscriptText(event.target.value)}
                  disabled={loading}
                  rows={12}
                  placeholder={"[00:00] Alice: Let's review the project.\n[00:15] Bob: I'll finish the report by Friday."}
                  className="w-full resize-y rounded-xl border border-slate-200 bg-white p-4 text-sm text-slate-900 outline-none placeholder:text-slate-400 focus:border-blue-500"
                />

                <p className="mt-2 text-xs text-slate-500">
                  {new TextEncoder().encode(transcriptText).length.toLocaleString()} / 2,097,152 bytes
                </p>
              </div>
            )}

{/* Error message */}
          {error && (
            <div
              role="alert"
              className="break-words rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-700"
            >
              <p className="mb-1 font-semibold">Unable to create meeting</p>
              <p>{error}</p>
            </div>
          )}

          {/* Success message */}
          {success && (
            <div
              role="status"
              className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700"
            >
              {success}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-3">
            <button
              type="button"
              onClick={() => router.push("/")}
              disabled={loading}
              className="rounded-xl border border-slate-200 bg-white px-5 py-3 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-50"
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
              className="rounded-xl bg-blue-600 text-white px-6 py-3 text-sm font-semibold shadow-lg shadow-blue-600/20 transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:scale-100"
            >
              {loading ? "Uploading..." : "Create Meeting →"}
            </button>
          </div>
        </form>
      </section>
    </main>
  );
}