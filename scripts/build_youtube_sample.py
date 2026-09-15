"""Build a local 40-second video sample from an authorized source copy.

This module performs no network access and does not download content from YouTube.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import tempfile

from fractions import Fraction
from pathlib import Path
from typing import Any

SAMPLE_ID = "youtube_oXn0KPPHzuY"
SOURCE_VIDEO_ID = "oXn0KPPHzuY"
SOURCE_URL = "https://www.youtube.com/watch?v=oXn0KPPHzuY"
FRAME_RATE = 25
FRAME_DURATION_US = 40_000
SOURCE_START_US = 160_000_000
SAMPLE_DURATION_US = 40_000_000
SOURCE_END_US = SOURCE_START_US + SAMPLE_DURATION_US
FRAME_COUNT = SAMPLE_DURATION_US // FRAME_DURATION_US
OUTPUT_WIDTH = 960
OUTPUT_HEIGHT = 540
HASH_CHUNK_SIZE = 1024 * 1024
START_TIME_TOLERANCE_SECONDS = 0.000001
DURATION_TOLERANCE_US = 10_000


class SampleBuildError(RuntimeError):
    """Raised when a local source cannot produce the normalized sample."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_sample(video=args.video, output=args.output)


def build_sample(
    *,
    video: Path,
    output: Path,
    ffmpeg: str = "ffmpeg",
    ffprobe: str = "ffprobe",
) -> dict[str, Any]:
    """Normalize the configured source interval and return the written manifest."""
    if not video.is_file():
        raise SampleBuildError(f"source video does not exist: {video}")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise SampleBuildError(f"output directory must be absent or empty: {output}")

    source = _probe_media(video, ffprobe=ffprobe, count_frames=False)
    if len(source["video_streams"]) != 1:
        raise SampleBuildError("source must contain exactly one video stream")
    source_video = source["video_streams"][0]
    if (
        int(source_video.get("width", 0)) <= 0
        or int(source_video.get("height", 0)) <= 0
    ):
        raise SampleBuildError("source video dimensions are unavailable")
    source_duration_us = _duration_us(source_video, source["format"])
    if source_duration_us < SOURCE_END_US:
        raise SampleBuildError(
            f"source video must extend through {SOURCE_END_US} microseconds"
        )

    with tempfile.TemporaryDirectory(prefix="tribuna-youtube-sample-") as temporary:
        staging = Path(temporary)
        sample_path = staging / "sample.mp4"
        _extract_sample(video, sample_path, ffmpeg=ffmpeg)
        sample = _probe_media(sample_path, ffprobe=ffprobe, count_frames=True)
        _validate_sample(sample)

        output_sha256 = _sha256(sample_path)
        manifest: dict[str, Any] = {
            "manifest_version": 1,
            "sample_id": SAMPLE_ID,
            "upstream": {
                "source_type": "developer_supplied_local_copy",
                "declared_video_id": SOURCE_VIDEO_ID,
                "canonical_url": SOURCE_URL,
                "source_filename": video.name,
                "source_sha256": _sha256(video),
                "codec": source_video.get("codec_name"),
                "pixel_format": source_video.get("pix_fmt"),
                "width": int(source_video["width"]),
                "height": int(source_video["height"]),
                "frame_rate": source_video.get("avg_frame_rate"),
                "duration_us": source_duration_us,
            },
            "selection": {
                "strategy": "source_presentation_timestamp_interval",
                "source_interval": {
                    "start_us": SOURCE_START_US,
                    "end_us": SOURCE_END_US,
                    "interval": "half-open",
                },
            },
            "video": {
                "filename": "sample.mp4",
                "codec": "h264",
                "pixel_format": "yuv420p",
                "width": OUTPUT_WIDTH,
                "height": OUTPUT_HEIGHT,
                "frame_rate": f"{FRAME_RATE}/1",
                "frame_count": FRAME_COUNT,
                "has_audio": False,
            },
            "media_interval": {
                "start_us": 0,
                "end_us": SAMPLE_DURATION_US,
                "interval": "half-open",
            },
            "timeline_mapping": {
                "media_start_us": 0,
                "media_end_us": SAMPLE_DURATION_US,
                "source_start_us": SOURCE_START_US,
                "source_end_us": SOURCE_END_US,
                "rate_numerator": 1,
                "rate_denominator": 1,
                "formula": f"source_time_us = media_time_us + {SOURCE_START_US}",
            },
            "transformation": {
                "timestamps_reset_to_zero": True,
                "audio_removed": True,
                "scaling": "960x540 using Lanczos resampling",
            },
            "checksums": {"sample.mp4": output_sha256},
        }
        manifest_path = staging / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        output.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sample_path, output / sample_path.name)
        shutil.copy2(manifest_path, output / manifest_path.name)
        return manifest


def _probe_media(path: Path, *, ffprobe: str, count_frames: bool) -> dict[str, Any]:
    command = [ffprobe, "-v", "error"]
    if count_frames:
        command.append("-count_frames")
    command.extend(
        [
            "-show_entries",
            (
                "stream=codec_type,codec_name,pix_fmt,width,height,avg_frame_rate,"
                "start_time,duration,nb_read_frames:format=start_time,duration"
            ),
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise SampleBuildError(f"required executable not found: {ffprobe}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "ffprobe could not read the source"
        raise SampleBuildError(detail) from error

    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    return {
        "video_streams": [
            stream for stream in streams if stream.get("codec_type") == "video"
        ],
        "audio_streams": [
            stream for stream in streams if stream.get("codec_type") == "audio"
        ],
        "format": payload.get("format", {}),
    }


def _extract_sample(source: Path, destination: Path, *, ffmpeg: str) -> None:
    video_filter = (
        f"trim=start={SOURCE_START_US / 1_000_000:g}:"
        f"end={SOURCE_END_US / 1_000_000:g},"
        "setpts=PTS-STARTPTS,"
        f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:flags=lanczos,"
        f"fps={FRAME_RATE}"
    )
    command = [
        ffmpeg,
        "-v",
        "error",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-vf",
        video_filter,
        "-frames:v",
        str(FRAME_COUNT),
        "-r",
        str(FRAME_RATE),
        "-an",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(destination),
    ]
    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
    except FileNotFoundError as error:
        raise SampleBuildError(f"required executable not found: {ffmpeg}") from error
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() or "ffmpeg could not build the sample"
        raise SampleBuildError(detail) from error


def _validate_sample(media: dict[str, Any]) -> None:
    videos = media["video_streams"]
    if len(videos) != 1:
        raise SampleBuildError("normalized sample must contain one video stream")
    if media["audio_streams"]:
        raise SampleBuildError("normalized sample must not contain audio")

    video = videos[0]
    actual = {
        "codec": video.get("codec_name"),
        "pixel_format": video.get("pix_fmt"),
        "width": int(video["width"]),
        "height": int(video["height"]),
        "frame_rate": Fraction(video["avg_frame_rate"]),
        "frame_count": int(video.get("nb_read_frames", 0)),
    }
    expected = {
        "codec": "h264",
        "pixel_format": "yuv420p",
        "width": OUTPUT_WIDTH,
        "height": OUTPUT_HEIGHT,
        "frame_rate": Fraction(FRAME_RATE, 1),
        "frame_count": FRAME_COUNT,
    }
    if actual != expected:
        raise SampleBuildError(f"normalized sample does not match contract: {actual}")

    start_time = float(media["format"].get("start_time", "nan"))
    duration_us = _seconds_to_us(media["format"].get("duration"))
    if (
        not math.isfinite(start_time)
        or abs(start_time) > START_TIME_TOLERANCE_SECONDS
        or abs(duration_us - SAMPLE_DURATION_US) > DURATION_TOLERANCE_US
    ):
        raise SampleBuildError("normalized sample has invalid timestamps or duration")


def _duration_us(stream: dict[str, Any], container: dict[str, Any]) -> int:
    value = stream.get("duration") or container.get("duration")
    if value is None:
        raise SampleBuildError("source video duration is unavailable")
    return _seconds_to_us(value)


def _seconds_to_us(value: object) -> int:
    try:
        seconds = float(str(value))
    except (TypeError, ValueError) as error:
        raise SampleBuildError(f"invalid media duration: {value!r}") from error
    if not math.isfinite(seconds):
        raise SampleBuildError(f"invalid media duration: {value!r}")
    return round(seconds * 1_000_000)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    main()
