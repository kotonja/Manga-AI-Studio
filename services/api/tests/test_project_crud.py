def test_project_crud_page_panel_and_job(client) -> None:
    create_response = client.post(
        "/projects",
        json={
            "name": "Ink Circuit",
            "description": "Cyberpunk manga pilot",
            "style_prompt": "Sharp black inks and expressive paneling",
        },
    )
    assert create_response.status_code == 201
    project = create_response.json()
    assert project["name"] == "Ink Circuit"

    list_response = client.get("/projects")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    detail_response = client.get(f"/projects/{project['id']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["pages"] == []

    page_response = client.post(f"/projects/{project['id']}/pages", json={"width": 1200, "height": 1800})
    assert page_response.status_code == 201
    page = page_response.json()
    assert page["page_number"] == 1
    assert page["width"] == 1200

    panel_response = client.post(
        f"/pages/{page['id']}/panels",
        json={"x": 40, "y": 60, "width": 500, "height": 360, "prompt": "Hero enters the alley"},
    )
    assert panel_response.status_code == 201
    panel = panel_response.json()
    assert panel["prompt"] == "Hero enters the alley"

    detail_response = client.get(f"/projects/{project['id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["pages"]) == 1
    assert len(detail["pages"][0]["panels"]) == 1

    job_response = client.post("/jobs/mock-render-panel", json={"panel_id": panel["id"]})
    assert job_response.status_code == 202
    job = job_response.json()
    assert job["status"] == "succeeded"
    assert job["provider"] == "mock"

    get_job_response = client.get(f"/jobs/{job['id']}")
    assert get_job_response.status_code == 200
    assert get_job_response.json()["render"] is not None

    provider_job_response = client.post(
        "/jobs/render-panel",
        json={"panel_id": panel["id"], "provider_name": "mock", "options": {"seed": 7}},
    )
    assert provider_job_response.status_code == 202
    provider_job = provider_job_response.json()
    assert provider_job["status"] == "succeeded"
    assert provider_job["provider"] == "mock"
    assert provider_job["input_payload"]["options"]["seed"] == 7


def test_missing_project_returns_404(client) -> None:
    response = client.get("/projects/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_project_accepts_long_form_description(client) -> None:
    long_description = "\n\n".join(
        [
            "Aether Crown follows four sky-born rivals through a vertical fantasy world.",
            "Everyone can fly, but each soul shapes Aether into a unique resonance.",
            "The Low Sky hides buried kingdoms, broken seals, and a throne wound below the city.",
        ]
        * 120
    )

    response = client.post(
        "/projects",
        json={"name": "Aether Crown", "description": long_description},
    )

    assert response.status_code == 201
    project = response.json()
    assert project["description"] == long_description
