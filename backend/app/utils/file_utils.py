from pathlib import Path

from app.core.config import settings


def get_file_extension(
    filename: str,
) -> str:
    """
    Return a lowercase file extension.
    """

    return Path(filename).suffix.lower()


def is_audio_file(
    filename: str,
) -> bool:
    """
    Check whether a file is an allowed audio file.
    """

    extension = get_file_extension(filename)

    return extension in settings.allowed_audio_extensions


def is_video_file(
    filename: str,
) -> bool:
    """
    Check whether a file is an allowed video file.
    """

    extension = get_file_extension(filename)

    return extension in settings.allowed_video_extensions


def is_supported_media_file(
    filename: str,
) -> bool:
    """
    Check whether the file is supported by the system.
    """

    return (
        is_audio_file(filename)
        or is_video_file(filename)
    )


def get_media_type(
    filename: str,
) -> str:
    """
    Return the general media type.
    """

    if is_audio_file(filename):
        return "audio"

    if is_video_file(filename):
        return "video"

    return "unknown"


def get_safe_filename(
    filename: str,
) -> str:
    """
    Remove directory components from a filename.
    """

    return Path(filename).name


def format_file_size(
    size_bytes: int,
) -> str:
    """
    Convert bytes into a human-readable size.
    """

    if size_bytes < 1024:
        return f"{size_bytes} B"

    if size_bytes < 1024**2:
        return f"{size_bytes / 1024:.2f} KB"

    if size_bytes < 1024**3:
        return f"{size_bytes / 1024**2:.2f} MB"

    return f"{size_bytes / 1024**3:.2f} GB"