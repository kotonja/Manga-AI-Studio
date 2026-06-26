def test_provider_registry_reports_missing_openai_key(client) -> None:
    response = client.get("/providers")
    assert response.status_code == 200
    providers = {provider["name"]: provider for provider in response.json()}

    assert providers["mock"]["configured"] is True
    assert providers["mock"]["capabilities"]["supports_image_generation"] is True
    assert providers["openai"]["configured"] is False
    assert "OPENAI_API_KEY" in providers["openai"]["missing_env_vars"]

    health = client.get("/providers/openai/health")
    assert health.status_code == 200
    assert health.json()["status"] == "not_configured"


def test_panel_render_dry_run_validates_provider_without_paid_call(client) -> None:
    _project, _page, panel = create_project_page_panel(client)

    mock_response = client.post(
        f"/panels/{panel['id']}/render-dry-run",
        json={"provider_name": "mock", "render_mode": "draft", "seed": 101},
    )
    assert mock_response.status_code == 200
    mock = mock_response.json()
    assert mock["provider_configured"] is True
    assert mock["can_render"] is True
    assert mock["estimated_cost"]["estimated_cost_usd"] == 0.0
    assert mock["prompt"]["positive_prompt"]

    openai_response = client.post(
        f"/panels/{panel['id']}/render-dry-run",
        json={"provider_name": "openai", "render_mode": "draft", "seed": 101},
    )
    assert openai_response.status_code == 200
    openai = openai_response.json()
    assert openai["provider_configured"] is False
    assert openai["can_render"] is False
    assert any("not configured" in warning.lower() for warning in openai["warnings"])


def test_provider_failure_stores_safe_error_and_retry_with_mock_works(client) -> None:
    _project, _page, panel = create_project_page_panel(client)

    failed_response = client.post(
        f"/panels/{panel['id']}/render",
        json={"provider_name": "openai", "render_mode": "draft", "seed": 202},
    )
    assert failed_response.status_code == 202
    failed_job = failed_response.json()["job"]
    assert failed_job["status"] == "failed"
    assert "OPENAI_API_KEY" in failed_job["error_message"]
    assert failed_job["output_payload"]["retry_provider"] == "mock"
    assert failed_job["output_payload"]["error_metadata"]["retry_with_mock_available"] is True
    assert failed_job["output_payload"]["cost_metadata"]["provider"] == "openai"
    assert failed_job["output_payload"]["cost_metadata"]["completed_at"]

    retry_response = client.post(
        f"/panels/{panel['id']}/render",
        json={"provider_name": "mock", "render_mode": "draft", "seed": 202},
    )
    assert retry_response.status_code == 202
    retry_job = retry_response.json()["job"]
    assert retry_job["status"] == "succeeded"
    assert retry_job["output_payload"]["provider"] == "mock"
    assert retry_job["output_payload"]["cost_metadata"]["estimated_cost"]["estimated_cost_usd"] == 0.0


def create_project_page_panel(client):
    project = client.post("/projects", json={"name": "Provider Battle", "description": "Provider tests"}).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 640, "height": 960}).json()
    panel_response = client.post(
        f"/pages/{page['id']}/panels",
        json={
            "x": 80,
            "y": 100,
            "width": 260,
            "height": 220,
            "reading_order": 1,
            "prompt": "A lonely swordsman protects a ghost child.",
        },
    )
    assert panel_response.status_code == 201
    return project, page, panel_response.json()
