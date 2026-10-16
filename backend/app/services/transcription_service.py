from pathlib import Path
from typing import Any

from faster_whisper import WhisperModel

from app.core.config import settings


class TranscriptionService:
    """
    Converts audio/video meeting files into timestamped
    transcript segments using Faster-Whisper.
    """

    def __init__(self) -> None:
        self.model: WhisperModel | None = None

    def _load_model(self) -> WhisperModel:
        """
        Load Whisper lazily so the model is not loaded during
        normal backend startup.
        """

        if self.model is None:
            self.model = WhisperModel(
                settings.WHISPER_MODEL,
                device="cpu",
                compute_type="int8",
            )

        return self.model

    def transcribe(
        self,
        file_path: str,
    ) -> dict[str, Any]:

        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(
                f"Media file not found: {file_path}"
            )

        model = self._load_model()

        segments, info = model.transcribe(
            str(path),
            beam_size=5,
            vad_filter=True,
            vad_parameters={
                "min_silence_duration_ms": 500,
            },
            word_timestamps=False,
        )

        transcript_segments: list[dict[str, Any]] = []

        sequence_number = 0

        for segment in segments:

            text = segment.text.strip()

            if not text:
                continue

            transcript_segments.append(
                {
                    "speaker_label": None,
                    "speaker_name": None,
                    "text": text,
                    "start_time": float(
                        segment.start
                    ),
                    "end_time": float(
                        segment.end
                    ),
                    "sequence_number": sequence_number,
                }
            )

            sequence_number += 1

        duration = 0.0

        if transcript_segments:
            duration = max(
                segment["end_time"]
                for segment in transcript_segments
            )

        return {
            "language": getattr(
                info,
                "language",
                None,
            ),
            "language_probability": float(
                getattr(
                    info,
                    "language_probability",
                    0.0,
                )
                or 0.0
            ),
            "duration": duration,
            "segments": transcript_segments,
        }

    def get_plain_text(
        self,
        transcription: dict[str, Any],
    ) -> str:

        lines: list[str] = []

        for segment in transcription.get(
            "segments",
            [],
        ):

            speaker = (
                segment.get("speaker_name")
                or segment.get("speaker_label")
                or "Speaker"
            )

            text = segment.get(
                "text",
                "",
            ).strip()

            if text:
                lines.append(
                    f"{speaker}: {text}"
                )

        return "\n".join(lines)

    def get_segment_count(
        self,
        transcription: dict[str, Any],
    ) -> int:

        return len(
            transcription.get(
                "segments",
                [],
            )
        )


transcription_service = TranscriptionService()