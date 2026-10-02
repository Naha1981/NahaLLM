import httpx
import pytest

from app.config import Settings
from app.media import MediaProviderError, clear_jobs, get_image_to_video_job, submit_image_to_video


@pytest.fixture(autouse=True)
def reset_jobs():
    clear_jobs()
    yield
    clear_jobs()


@pytest.mark.asyncio
async def test_media_submit_and_poll(monkeypatch):
    settings = Settings(
        nahallm_api_keys="test-key",
        nahamedia_enabled=True,
        spyce_api_key="spyce-key",
        spyce_i2v_submit_url="https://example.test/i2v",
        spyce_i2v_status_url_template="https://example.test/i2v/{job_id}",
    )

    calls = []

    class FakeClient:
        async def post(self, *args, **kwargs):
            calls.append(("post", args, kwargs))
            return httpx.Response(200, json={"job_id": "spyce-123", "status": "queued"})

        async def get(self, *args, **kwargs):
            calls.append(("get", args, kwargs))
            return httpx.Response(200, json={"status": "completed", "video_url": "https://cdn.example/video.mp4"})

    monkeypatch.setattr("app.media.http_client", lambda: FakeClient())

    job = await submit_image_to_video(
        image_url="https://cdn.example/input.jpg",
        prompt="A gentle camera push-in with natural movement",
        model=None,
        duration_seconds=6,
        aspect_ratio="16:9",
        resolution="720p",
        settings=settings,
    )

    assert job.provider == "spyce"
    assert job.provider_job_id == "spyce-123"
    assert job.status == "queued"

    updated = await get_image_to_video_job(job.id, settings)

    assert updated is not None
    assert updated.status == "completed"
    assert updated.video_url == "https://cdn.example/video.mp4"
    assert calls[0][2]["json"]["image_url"] == "https://cdn.example/input.jpg"
    assert calls[0][2]["json"]["prompt"].startswith("A gentle camera")
    assert calls[0][2]["json"]["duration_seconds"] == 6
    assert calls[0][2]["json"]["aspect_ratio"] == "16:9"


@pytest.mark.asyncio
async def test_media_disabled_without_provider_config():
    settings = Settings(
        nahallm_api_keys="test-key",
        nahamedia_enabled=False,
    )

    with pytest.raises(MediaProviderError):
        await submit_image_to_video(
            image_url="https://cdn.example/input.jpg",
            prompt="animate",
            model=None,
            duration_seconds=None,
            aspect_ratio=None,
            resolution=None,
            settings=settings,
        )
