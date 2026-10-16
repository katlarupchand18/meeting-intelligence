export type MeetingType =
  | "business"
  | "academic"
  | "political"
  | "team"
  | "client"
  | "interview"
  | "personal"
  | "other";

export type MeetingStatus =
  | "created"
  | "processing"
  | "transcribed"
  | "analyzed"
  | "completed"
  | "failed";

export type CommitmentStatus =
  | "pending"
  | "in_progress"
  | "completed"
  | "overdue"
  | "blocked"
  | "cancelled";

export type CommitmentStrength =
  | "explicit"
  | "implicit"
  | "tentative";

export type DecisionStatus =
  | "proposed"
  | "accepted"
  | "rejected"
  | "changed"
  | "superseded";

export type EvidenceType =
  | "transcript"
  | "decision"
  | "commitment"
  | "context";

export interface Participant {
  id: string;
  meeting_id: string;
  name: string;
  role?: string | null;
  speaker_label?: string | null;
  email?: string | null;
}

export interface TranscriptSegment {
  id: string;
  meeting_id: string;
  speaker_id?: string | null;
  speaker_label?: string | null;
  text: string;
  start_time?: number | null;
  end_time?: number | null;
  confidence?: number | null;
}

export interface Meeting {
  id: string;
  title: string;
  description?: string | null;
  meeting_type: MeetingType | string;
  status: MeetingStatus | string;

  language?: string | null;
  duration_seconds?: number | null;

  audio_file_path?: string | null;
  video_file_path?: string | null;

  created_at: string;
  updated_at?: string | null;

  participants?: Participant[];
}

export interface Commitment {
  id: string;
  meeting_id: string;

  owner_id?: string | null;
  owner_name?: string | null;

  title: string;
  description: string;

  status: CommitmentStatus | string;
  strength: CommitmentStrength | string;

  deadline?: string | null;

  confidence?: number | null;

  created_at: string;
  updated_at?: string | null;

  evidence?: Evidence[];
}

export interface Decision {
  id: string;
  meeting_id: string;

  title: string;
  description: string;

  status: DecisionStatus | string;

  confidence?: number | null;

  changed_from_decision_id?: string | null;

  created_at: string;

  evidence?: Evidence[];
}

export interface Evidence {
  id: string;

  meeting_id: string;

  transcript_segment_id?: string | null;
  commitment_id?: string | null;
  decision_id?: string | null;

  evidence_type: EvidenceType | string;

  quote?: string | null;

  start_time?: number | null;
  end_time?: number | null;

  confidence?: number | null;

  created_at: string;
}

export interface AccountabilitySummary {
  total_commitments: number;
  completed_commitments: number;
  pending_commitments: number;
  overdue_commitments: number;
  unassigned_commitments: number;
  blocked_commitments: number;
  completion_rate: number;
}

export interface AccountabilityOverview {
  total_meetings: number;
  total_commitments: number;
  total_decisions: number;
  overdue_commitments: number;

  upcoming?: Commitment[];
  overdue?: Commitment[];
  blocked?: Commitment[];
  unassigned?: Commitment[];

  summary?: AccountabilitySummary;
}

export interface MeetingAnalysis {
  meeting_id: string;

  summary?: string | null;

  key_points?: string[];

  decisions?: Decision[];

  commitments?: Commitment[];

  participants?: Participant[];

  risks?: string[];

  unanswered_questions?: string[];

  confidence?: number | null;
}

export interface MemorySearchResult {
  id: string;
  meeting_id: string;

  content: string;

  similarity?: number;

  metadata?: Record<string, unknown>;
}

export interface ApiResponse<T> {
  success: boolean;
  message?: string;
  data?: T;
  error?: string;
}