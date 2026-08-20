from app.core.config import get_settings


def test_development_actor_provider_is_guarded(client, users):
    settings = get_settings()
    previous = settings.actor_provider
    settings.actor_provider = "external"
    try:
        response = client.get(
            "/api/applications/mine",
            headers={"X-Actor-Id": users["candidate"]["id"]},
        )
    finally:
        settings.actor_provider = previous

    assert response.status_code == 403
