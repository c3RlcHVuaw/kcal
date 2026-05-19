from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


class MediaProcessingError(RuntimeError):
    pass


def extract_frame_from_video(video_bytes: bytes) -> bytes:
    return extract_frames_from_video(video_bytes, limit=1)[0]


def extract_frames_from_video(video_bytes: bytes, limit: int = 8) -> list[bytes]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / "input.mp4"
        input_path.write_bytes(video_bytes)

        duration = _probe_duration(input_path)
        if duration is not None:
            for index, timestamp in enumerate(_sample_timestamps(duration, limit), start=1):
                output_path = Path(tmp_dir) / f"frame_{index:02d}.jpg"
                command = [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{timestamp:.3f}",
                    "-i",
                    str(input_path),
                    "-an",
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=2200:-1:flags=lanczos,unsharp=5:5:0.8:3:3:0.4",
                    "-q:v",
                    "2",
                    str(output_path),
                ]
                try:
                    _run_ffmpeg(command)
                except MediaProcessingError:
                    continue
        else:
            output_pattern = Path(tmp_dir) / "frame_%02d.jpg"
            command = [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-an",
                "-vf",
                "fps=3,scale=2200:-1:flags=lanczos,unsharp=5:5:0.8:3:3:0.4",
                "-frames:v",
                str(limit),
                "-q:v",
                "2",
                str(output_pattern),
            ]
            _run_ffmpeg(command)

        frames = sorted(Path(tmp_dir).glob("frame_*.jpg"))
        if not frames:
            raise MediaProcessingError("Could not extract video frame")
        return [frame.read_bytes() for frame in frames]


def convert_audio_to_mp3(audio_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmp_dir:
        input_path = Path(tmp_dir) / "input.oga"
        output_path = Path(tmp_dir) / "voice.mp3"
        input_path.write_bytes(audio_bytes)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-vn",
            "-acodec",
            "libmp3lame",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
        ]
        _run_ffmpeg(command)
        if not output_path.exists():
            raise MediaProcessingError("Could not convert audio")
        return output_path.read_bytes()


def _run_ffmpeg(command: list[str]) -> None:
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise MediaProcessingError(result.stderr[-500:])


def _probe_duration(input_path: Path) -> float | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(input_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    try:
        duration = float(json.loads(result.stdout)["format"]["duration"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return duration if duration > 0 else None


def _sample_timestamps(duration: float, limit: int) -> list[float]:
    if limit <= 1:
        return [0.0]
    if duration <= 0:
        return [0.0]

    last_timestamp = max(duration - 0.1, 0.0)
    frame_count = max(limit, 1)
    if frame_count == 1:
        return [0.0]

    step = last_timestamp / (frame_count - 1)
    return [round(step * index, 3) for index in range(frame_count)]
