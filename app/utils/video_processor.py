# app/utils/video_processor.py
import os
import subprocess
import logging
import uuid
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


def compress_video(input_file_path: str, output_quality: str = "medium") -> str:
    """
    Compress a video file using FFmpeg.

    Args:
        input_file_path: Path to the input video file
        output_quality: Compression quality (low, medium, high)

    Returns:
        Path to the compressed video file
    """
    try:
        # Generate a temporary filename
        tmp_dir = tempfile.gettempdir()
        output_filename = f"{uuid.uuid4()}.mp4"
        output_file_path = os.path.join(tmp_dir, output_filename)

        # Define quality presets
        quality_presets = {
            "low": ["-vf", "scale=-2:480", "-crf", "28", "-preset", "veryfast"],
            "medium": ["-vf", "scale=-2:720", "-crf", "23", "-preset", "medium"],
            "high": ["-vf", "scale=-2:1080", "-crf", "18", "-preset", "slow"],
        }

        quality_settings = quality_presets.get(
            output_quality, quality_presets["medium"]
        )

        # Use the full path to FFmpeg
        command = [
            "/usr/bin/ffmpeg",
            "-i",
            input_file_path,
            *quality_settings,
            "-c:v",
            "libx264",  # Video codec
            "-c:a",
            "aac",  # Audio codec
            "-movflags",
            "+faststart",  # Optimize for web streaming
            output_file_path,
        ]

        # Run the compression process
        process = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if process.returncode != 0:
            logger.error(f"FFmpeg error: {process.stderr}")
            raise Exception(f"Video compression failed: {process.stderr}")

        return output_file_path

    except Exception as e:
        logger.error(f"Error compressing video: {str(e)}")
        # If compression fails, return the original file path
        logger.info(f"Returning original uncompressed video file")
        return input_file_path
