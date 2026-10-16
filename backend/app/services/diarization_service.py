from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import torch
import torchaudio
from pyannote.audio import Pipeline

from app.core.config import settings


class DiarizationService:
    """Speaker diarization using PyAnnote Community-1."""

    def __init__(self) -> None:
        self.pipeline: Any = None
        self._load_error: str | None = None

    def _load_pipeline(self) -> Any:
        """Load the diarization model lazily."""

        if self.pipeline is not None:
            return self.pipeline

        token = settings.HUGGINGFACE_TOKEN.strip()

        if not token:
            raise RuntimeError(
                "HUGGINGFACE_TOKEN is missing from backend/.env."
            )

        try:
            self.pipeline = Pipeline.from_pretrained(
                "pyannote/speaker-diarization-community-1",
                token=token,
            )

            try:
                if torch.backends.mps.is_available():
                    self.pipeline.to(torch.device("mps"))
                else:
                    self.pipeline.to(torch.device("cpu"))
            except Exception as exc:
                print(
                    f"[Diarization] Device configuration warning: {exc}"
                )

            self._load_error = None
            return self.pipeline

        except Exception as exc:
            self._load_error = str(exc)
            raise RuntimeError(
                f"Could not load PyAnnote: {exc}"
            ) from exc

    def is_available(self) -> bool:
        return self.pipeline is not None

    def get_status(self) -> dict[str, Any]:
        return {
            "available": self.is_available(),
            "provider": "pyannote.audio",
            "model": "pyannote/speaker-diarization-community-1",
            "error": self._load_error,
        }

    @staticmethod
    def _normalize_audio(
        source: Path,
        destination: str,
    ) -> None:
        """Convert audio to mono, 16 kHz PCM WAV."""

        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(source),
                    "-vn",
                    "-ac",
                    "1",
                    "-ar",
                    "16000",
                    "-c:a",
                    "pcm_s16le",
                    destination,
                ],
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )

        except FileNotFoundError as exc:
            raise RuntimeError(
                "FFmpeg was not found. Install it with brew install ffmpeg."
            ) from exc

        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                "Audio normalization timed out."
            ) from exc

        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "Audio normalization failed: "
                f"{(exc.stderr or str(exc)).strip()}"
            ) from exc

    def diarize(
        self,
        file_path: str,
    ) -> list[dict[str, Any]]:
        """
        Detect speaker turns.

        Returns:
            [{"speaker_label": "SPEAKER_00",
              "start_time": 0.0,
              "end_time": 2.5}, ...]
        """

        path = Path(file_path)

        if not path.is_file():
            raise FileNotFoundError(
                f"Audio file not found: {file_path}"
            )

        pipeline = self._load_pipeline()
        temp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".wav",
                prefix="meeting_diarization_",
                delete=False,
            ) as temp_file:
                temp_path = temp_file.name

            print("[Diarization] Normalizing audio...")
            self._normalize_audio(path, temp_path)

            print("[Diarization] Loading normalized waveform...")

            waveform, sample_rate = torchaudio.load(temp_path)

            # Community-1 expects a waveform shaped (channels, samples).
            waveform = waveform.to(torch.float32)

            # Pass audio in memory rather than as a filename.
            print("[Diarization] Running PyAnnote...")

            output = pipeline(
                {
                    "waveform": waveform,
                    "sample_rate": sample_rate,
                    "uri": path.stem,
                }
            )

            diarization = output.exclusive_speaker_diarization
            results: list[dict[str, Any]] = []

            for turn, _, speaker in diarization.itertracks(
                yield_label=True
            ):
                results.append(
                    {
                        "speaker_label": str(speaker),
                        "start_time": float(turn.start),
                        "end_time": float(turn.end),
                    }
                )

            speakers = sorted(
                {
                    item["speaker_label"]
                    for item in results
                }
            )

            print(
                f"[Diarization] Completed: {len(speakers)} "
                f"speakers, {len(results)} speaker turns."
            )

            self._load_error = None
            return results

        except Exception as exc:
            self._load_error = str(exc)
            print(
                f"[Diarization] Error: "
                f"{type(exc).__name__}: {exc}"
            )
            raise

        finally:
            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError as exc:
                    print(
                        f"[Diarization] Temporary file cleanup warning: {exc}"
                    )

    @staticmethod
    def _calculate_overlap(
        transcript_start: float,
        transcript_end: float,
        speaker_start: float,
        speaker_end: float,
    ) -> float:
        """Calculate temporal overlap between two segments."""

        return max(
            0.0,
            min(transcript_end, speaker_end)
            - max(transcript_start, speaker_start),
        )

    def attach_speakers(
        self,
        transcript_segments: list[dict[str, Any]],
        speaker_segments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Assign the speaker with the greatest time overlap."""

        for transcript in transcript_segments:
            transcript_start = float(transcript["start_time"])
            transcript_end = float(transcript["end_time"])

            best_speaker: str | None = None
            best_overlap = 0.0

            for speaker in speaker_segments:
                overlap = self._calculate_overlap(
                    transcript_start,
                    transcript_end,
                    float(speaker["start_time"]),
                    float(speaker["end_time"]),
                )

                if overlap > best_overlap:
                    best_overlap = overlap
                    best_speaker = speaker["speaker_label"]

            transcript["speaker_label"] = best_speaker

        return transcript_segments


diarization_service = DiarizationService()