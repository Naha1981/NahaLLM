from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx

from .config import Settings
from .providers import http_client


class MediaProviderError(Exception):
    def __init__(self, provider: str, status_code: int | None, detail: str):
        self.provider = provider
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


@dataclass
class MediaJob:
    id: str
    provider: str
    provider_job_id: str
    status: str
    video_url: str | None
    error: str | None
    created_at: str


_jobs: dict[str, MediaJob] = {}


def _extract_video_url(payload: dict[str, Any]) -> str | None:
    for key in ("video_url", "output_url", "url"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value

    output = payload.get("output")
    if isinstance(output, dict):
        return _extract_video_url(output)

    if isinstance(output, list):
        for item in output:
            if isinstance(item, str) and item:
                return item
            if isinstance(item, dict):
                url = _extract_video_url(item)
                if url:
                    return url

    return None


def _extract_provider_job_id(payload: dict[str, Any]) -> str | None:
    for key in ("id", "job_id", "task_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_status(payload: dict[str, Any]) -> str:
    value = payload.get("status")
    return value if isinstance(value, str) and value else "submitted"


def media_enabled(settings: Settings) -> bool:
    return settings.nahamedia_enabled and bool(
        settings.spyce_api_key
        and settings.spyce_i2v_submit_url
        and settings.spyce_i2v_status_url_template
    )


def _spyce_headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.spyce_api_key}",
        "Content-Type": "application/json",
    }


async def submit_image_to_video(
    *,
    image_url: str,
    prompt: str,
    model: str | None,
    duration_seconds: float | None,
    aspect_ratio: str | None,
    resolution: str | None,
    settings: Settings,
) -> MediaJob:
    if not media_enabled(settings):
        raise MediaProviderError("spyce", 503, "Image-to-video provider is not configured")

    requested_model = model or settings.spyce_i2v_model
    payload = {
        "image_url": image_url,
        "prompt": prompt,
        "model": requested_model,
    }

    for key, value in (
        ("duration_seconds", duration_seconds),
        ("aspect_ratio", aspect_ratio),
        ("resolution", resolution),
    ):
        if value is not None:
            payload[key] = value

    try:
        response = await http_client().post(
            settings.spyce_i2v_submit_url.rstrip("/"),
            headers=_spyce_headers(settings),
            json=payload,
            timeout=settings.nahallm_media_request_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        raise MediaProviderError("spyce", None, str(exc)) from exc

    if response.status_code >= 400:
        raise MediaProviderError(
            "spyce",
            response.status_code,
            response.text[:1000],
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise MediaProviderError("spyce", response.status_code, "Provider returned non-JSON response") from exc

    provider_job_id = _extract_provider_job_id(data)
    if not provider_job_id:
        raise MediaProviderError("spyce", response.status_code, "Provider response did not include a job id")

    job = MediaJob(
        id="nmedia_" + uuid.uuid4().hex[:16],
        provider="spyce",
        provider_job_id=provider_job_id,
        status=_extract_status(data),
        video_url=_extract_video_url(data),
        error=None,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _jobs[job.id] = job
    return job


async def get_image_to_video_job(job_id: str, settings: Settings) -> MediaJob | None:
    job = _jobs.get(job_id)
    if job is None:
        return None

    if job.status.lower() in {"completed", "succeeded", "failed", "error", "canceled", "cancelled"}:
        return job

    status_url = settings.spyce_i2v_status_url_template.format(job_id=job.provider_job_id)

    try:
        response = await http_client().get(
            status_url,
            headers=_spyce_headers(settings),
            timeout=settings.nahallm_media_request_timeout_seconds,
        )
    except httpx.HTTPError as exc:
        job.status = "provider_error"
        job.error = str(exc)
        return job

    if response.status_code >= 400:
        job.status = "provider_error"
        job.error = response.text[:1000]
        return job

    try:
        data = response.json()
    except ValueError:
        job.status = "provider_error"
        job.error = "Provider returned non-JSON response"
        return job

    job.status = _extract_status(data)
    job.video_url = _extract_video_url(data) or job.video_url

    if job.status.lower() in {"failed", "error", "canceled", "cancelled"}:
        error = data.get("error") or data.get("message")
        job.error = str(error) if error else "Provider reported job failure"

    return job


def clear_jobs() -> None:
    _jobs.clear()
