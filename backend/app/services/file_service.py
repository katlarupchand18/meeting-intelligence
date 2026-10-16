from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import settings


class FileService:
    """
    Handles meeting audio/video file storage and validation.
    """

    def __init__(self) -> None:
        self.upload_dir = Path(settings.UPLOAD_DIR)
        self.upload_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    # ---------------------------------------------------------
    # Validation
    # ---------------------------------------------------------

    def validate_file(
        self,
        file: UploadFile,
    ) -> None:
        """
        Validate filename and file extension.
        """

        if not file.filename:
            raise ValueError("No filename was provided.")

        extension = Path(file.filename).suffix.lower()

        allowed_extensions = (
            settings.allowed_audio_extensions
            + settings.allowed_video_extensions
        )

        if extension not in allowed_extensions:
            raise ValueError(
                f"Unsupported file type: {extension}. "
                f"Allowed types: {', '.join(allowed_extensions)}"
            )

    # ---------------------------------------------------------
    # Save File
    # ---------------------------------------------------------

    async def save_file(
        self,
        file: UploadFile,
    ) -> tuple[str, str]:
        """
        Save an uploaded meeting file.

        Returns:
            tuple[str, str]:
                (stored_file_path, original_filename)
        """

        self.validate_file(file)

        original_filename = Path(
            file.filename or "meeting"
        ).name

        extension = Path(
            original_filename
        ).suffix.lower()

        unique_filename = (
            f"{uuid4().hex}{extension}"
        )

        destination = (
            self.upload_dir / unique_filename
        )

        max_size = settings.max_upload_size_bytes

        total_size = 0

        try:
            with destination.open("wb") as output:

                while True:
                    chunk = await file.read(1024 * 1024)

                    if not chunk:
                        break

                    total_size += len(chunk)

                    if total_size > max_size:
                        destination.unlink(
                            missing_ok=True
                        )

                        raise ValueError(
                            f"File exceeds the maximum "
                            f"allowed size of "
                            f"{settings.MAX_UPLOAD_SIZE_MB} MB."
                        )

                    output.write(chunk)

        except Exception:
            destination.unlink(
                missing_ok=True
            )
            raise

        return str(destination), original_filename

    # ---------------------------------------------------------
    # Delete File
    # ---------------------------------------------------------

    def delete_file(
        self,
        file_path: str | None,
    ) -> bool:
        """
        Delete an uploaded file.
        """

        if not file_path:
            return False

        path = Path(file_path)

        if not path.exists():
            return False

        path.unlink()

        return True

    # ---------------------------------------------------------
    # File Exists
    # ---------------------------------------------------------

    def file_exists(
        self,
        file_path: str | None,
    ) -> bool:
        """
        Check whether an uploaded file exists.
        """

        if not file_path:
            return False

        return Path(file_path).exists()


file_service = FileService()