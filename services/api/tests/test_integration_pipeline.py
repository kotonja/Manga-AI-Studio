def test_endpoint_pipeline_from_story_to_export_download(client) -> None:
    project_response = client.post(
        "/projects",
        json={
            "name": "Integration Manga",
            "description": "A courier guards a forbidden map through a city of living ink.",
        },
    )
    assert project_response.status_code == 201
    project = project_response.json()

    story_response = client.post(
        f"/projects/{project['id']}/story/generate-bible",
        json={"premise": project["description"], "chapter_count": 1},
    )
    assert story_response.status_code == 201

    chapter_response = client.post(f"/projects/{project['id']}/story/generate-chapter-plan")
    assert chapter_response.status_code == 201
    chapter = chapter_response.json()[0]

    page_plan_response = client.post(f"/chapters/{chapter['id']}/story/generate-page-plans")
    assert page_plan_response.status_code == 201
    page_plan = page_plan_response.json()[0]
    assert len(page_plan["panels"]) == 2

    page_response = client.post(f"/projects/{project['id']}/pages", json={"width": 1000, "height": 1500})
    assert page_response.status_code == 201
    page = page_response.json()

    layout_response = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 1000,
            "height": 1500,
            "bleed": 40,
            "safe_margin": 80,
            "reading_direction": "rtl",
            "qa_overlay_enabled": False,
            "panels": [
                {
                    "x": 80,
                    "y": 100,
                    "width": 840,
                    "height": 560,
                    "reading_order": 1,
                    "prompt": page_plan["panels"][0]["visual_notes"],
                    "polygon": [
                        {"x": 80, "y": 100},
                        {"x": 920, "y": 100},
                        {"x": 920, "y": 660},
                        {"x": 80, "y": 660},
                    ],
                },
                {
                    "x": 80,
                    "y": 760,
                    "width": 840,
                    "height": 600,
                    "reading_order": 2,
                    "prompt": page_plan["panels"][1]["visual_notes"],
                    "polygon": [
                        {"x": 80, "y": 760},
                        {"x": 920, "y": 760},
                        {"x": 920, "y": 1360},
                        {"x": 80, "y": 1360},
                    ],
                },
            ],
        },
    )
    assert layout_response.status_code == 200
    panels = layout_response.json()["panels"]

    bubble_response = client.post(
        f"/panels/{panels[0]['id']}/bubbles",
        json={"kind": "speech", "x": 140, "y": 150, "width": 280, "height": 120, "text": "Keep moving."},
    )
    assert bubble_response.status_code == 201
    bubble_update = client.put(f"/bubbles/{bubble_response.json()['id']}", json={"text": "Keep moving!"})
    assert bubble_update.status_code == 200

    for index, panel in enumerate(panels, start=1):
        render_response = client.post(
            "/jobs/render-panel",
            json={"panel_id": panel["id"], "provider_name": "mock", "options": {"seed": 700 + index}},
        )
        assert render_response.status_code == 202
        render_job = render_response.json()
        assert render_job["status"] == "succeeded"

        job_detail = client.get(f"/jobs/{render_job['id']}")
        assert job_detail.status_code == 200
        assert job_detail.json()["render"] is not None

    composite_response = client.post(f"/pages/{page['id']}/compose")
    assert composite_response.status_code == 201
    assert composite_response.json()["width"] == 1000

    qa_response = client.post(f"/pages/{page['id']}/qa", json={"provider_name": "mock", "export_preset": "draft"})
    assert qa_response.status_code == 201
    assert qa_response.json()["blocking"] is False

    export_response = client.post(
        f"/projects/{project['id']}/exports",
        json={"format": "zip", "force": False, "options": {"source": "integration_test"}},
    )
    assert export_response.status_code == 201
    export = export_response.json()
    assert export["status"] == "succeeded"

    download = client.get(f"/exports/{export['id']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    assert len(download.content) > 100
