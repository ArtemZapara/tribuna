from __future__ import annotations

import hashlib
import json
import shutil
import subprocess

from pathlib import Path
from typing import Any

import pytest

from scripts.build_youtube_sample import (
    FRAME_COUNT,
    SAMPLE_DURATION_US,
    SOURCE_END_US,
    SOURCE_START_US,
    SampleBuildError,
    build_sample,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DESCRIPTOR = (
    ROOT / "packages" / "sample-inputs" / "youtube_oXn0KPPHzuY" / "source.json"
)


@pytest.fixture(scope="module", autouse=True)
def require_media_tools() -> None:
    assert shutil.which("ffmpeg"), "FFmpeg is required for media contract tests"
    assert shutil.which("ffprobe"), "ffprobe is required for media contract tests"


@pytest.fixture(scope="module")
def source_video(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("youtube-sample-source") / "source.mp4"
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "color=color=black:size=320x180:rate=25:duration=201",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000:duration=201",
            "-shortest",
            "-vf",
            "drawbox=x=0:y=0:w=iw:h=ih:color=white:t=fill:enable='gte(t,160)'",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(path),
        ]
    )
    return path


def test_source_descriptor_identifies_video_and_limits_usage() -> None:
    descriptor = json.loads(SOURCE_DESCRIPTOR.read_text(encoding="utf-8"))

    assert descriptor["video_id"] == "oXn0KPPHzuY"
    assert descriptor["canonical_url"] == (
        "https://www.youtube.com/watch?v=oXn0KPPHzuY"
    )
    assert descriptor["uploader"] == "Chepsi007"
    assert descriptor["observed_metadata"] == {
        "retrieved_on": "2026-09-14",
        "duration_seconds": 6866,
        "width": 1920,
        "height": 1080,
        "frame_rate": "25/1",
    }
    assert descriptor["sample_selection"] == {
        "source_start_us": SOURCE_START_US,
        "source_end_us": SOURCE_END_US,
        "interval": "half-open",
        "duration_us": SAMPLE_DURATION_US,
        "output_frame_rate": "25/1",
        "output_frame_count": FRAME_COUNT,
    }
    assert descriptor["usage"]["media_committed_to_repository"] is False
    assert descriptor["usage"]["acquisition"].endswith("yt-dlp")
    assert descriptor["usage"]["automated_by_application_or_ci"] is False
    notice = descriptor["usage"]["notice"].lower()
    assert "does not grant a licence" in notice
    assert "outside git" in notice


def test_builder_writes_normalized_video_and_manifest(
    tmp_path: Path, source_video: Path
) -> None:
    output = tmp_path / "output"
    returned = build_sample(video=source_video, output=output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    media = _probe(output / "sample.mp4")

    assert returned == manifest
    assert manifest["sample_id"] == "youtube_oXn0KPPHzuY"
    assert manifest["upstream"]["source_sha256"] == _sha256(source_video)
    assert manifest["selection"] == {
        "strategy": "source_presentation_timestamp_interval",
        "source_interval": {
            "start_us": SOURCE_START_US,
            "end_us": SOURCE_END_US,
            "interval": "half-open",
        },
    }
    assert manifest["media_interval"] == {
        "start_us": 0,
        "end_us": SAMPLE_DURATION_US,
        "interval": "half-open",
    }
    assert manifest["timeline_mapping"] == {
        "media_start_us": 0,
        "media_end_us": SAMPLE_DURATION_US,
        "source_start_us": SOURCE_START_US,
        "source_end_us": SOURCE_END_US,
        "rate_numerator": 1,
        "rate_denominator": 1,
        "formula": f"source_time_us = media_time_us + {SOURCE_START_US}",
    }
    assert manifest["checksums"] == {"sample.mp4": _sha256(output / "sample.mp4")}
    assert _first_frame_mean_luma(output / "sample.mp4") > 200

    videos = [stream for stream in media["streams"] if stream["codec_type"] == "video"]
    audios = [stream for stream in media["streams"] if stream["codec_type"] == "audio"]
    assert len(videos) == 1
    assert not audios
    assert videos[0]["codec_name"] == "h264"
    assert videos[0]["pix_fmt"] == "yuv420p"
    assert videos[0]["width"] == 960
    assert videos[0]["height"] == 540
    assert videos[0]["avg_frame_rate"] == "25/1"
    assert int(videos[0]["nb_read_frames"]) == FRAME_COUNT
    assert float(media["format"]["start_time"]) == pytest.approx(0.0, abs=1e-6)
    assert float(media["format"]["duration"]) == pytest.approx(40.0, abs=0.01)


def test_builder_rejects_missing_source_and_nonempty_output(
    tmp_path: Path, source_video: Path
) -> None:
    with pytest.raises(SampleBuildError, match="source video does not exist"):
        build_sample(video=tmp_path / "missing.mp4", output=tmp_path / "missing-out")

    output = tmp_path / "occupied"
    output.mkdir()
    (output / "existing.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(SampleBuildError, match="must be absent or empty"):
        build_sample(video=source_video, output=output)
    assert (output / "existing.txt").read_text(encoding="utf-8") == "keep"


def test_builder_rejects_short_and_audio_only_inputs(tmp_path: Path) -> None:
    short = tmp_path / "short.mp4"
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=320x180:rate=25:duration=0.2",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(short),
        ]
    )
    with pytest.raises(SampleBuildError, match="must extend through"):
        build_sample(video=short, output=tmp_path / "short-out")

    audio_only = tmp_path / "audio.m4a"
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=1000:sample_rate=48000:duration=1",
            "-c:a",
            "aac",
            str(audio_only),
        ]
    )
    with pytest.raises(SampleBuildError, match="exactly one video stream"):
        build_sample(video=audio_only, output=tmp_path / "audio-out")


def test_builder_reports_missing_media_tools(
    tmp_path: Path, source_video: Path
) -> None:
    with pytest.raises(SampleBuildError, match="required executable not found"):
        build_sample(
            video=source_video,
            output=tmp_path / "missing-ffprobe",
            ffprobe="tribuna-missing-ffprobe",
        )
    with pytest.raises(SampleBuildError, match="required executable not found"):
        build_sample(
            video=source_video,
            output=tmp_path / "missing-ffmpeg",
            ffmpeg="tribuna-missing-ffmpeg",
        )


def _run_ffmpeg(arguments: list[str]) -> None:
    subprocess.run(
        ["ffmpeg", "-v", "error", *arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _probe(path: Path) -> dict[str, Any]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-count_frames",
        "-show_entries",
        (
            "stream=codec_type,codec_name,pix_fmt,width,height,avg_frame_rate,"
            "nb_read_frames:format=start_time,duration"
        ),
        "-of",
        "json",
        str(path),
    ]
    return json.loads(
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _first_frame_mean_luma(path: Path) -> int:
    completed = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-vf",
            "scale=1:1,format=gray",
            "-f",
            "rawvideo",
            "-",
        ],
        check=True,
        capture_output=True,
    )
    assert len(completed.stdout) == 1
    return completed.stdout[0]
