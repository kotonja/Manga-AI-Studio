def page_layout_payload(x: int, y: int, width: int = 220, height: int = 180) -> dict:
    return {
        "width": 700,
        "height": 1000,
        "bleed": 16,
        "safe_margin": 48,
        "reading_direction": "ltr",
        "qa_overlay_enabled": False,
        "panels": [
            {
                "x": x,
                "y": y,
                "width": width,
                "height": height,
                "reading_order": 1,
                "prompt": "Versioned panel",
                "polygon": [
                    {"x": x, "y": y},
                    {"x": x + width, "y": y},
                    {"x": x + width, "y": y + height},
                    {"x": x, "y": y + height},
                ],
            }
        ],
    }


def test_snapshot_and_restore_previous_page_layout(client) -> None:
    project = client.post("/projects", json={"name": "Versioned Layout"}).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 700, "height": 1000}).json()

    first_layout = client.put(f"/pages/{page['id']}/layout", json=page_layout_payload(80, 100)).json()
    panel_id = first_layout["panels"][0]["id"]
    second_payload = page_layout_payload(260, 320)
    second_payload["panels"][0]["id"] = panel_id
    client.put(f"/pages/{page['id']}/layout", json=second_payload)

    versions = client.get(f"/projects/{project['id']}/versions").json()
    layout_versions = [
        version
        for version in versions
        if version["entity_type"] == "layout" and version["reason"] == "before_page_layout_update"
    ]
    assert layout_versions
    previous_layout_version = layout_versions[0]
    assert previous_layout_version["snapshot_json"]["panels"][0]["x"] == 80

    restore = client.post(f"/versions/{previous_layout_version['id']}/restore")

    assert restore.status_code == 200
    restored = client.get(f"/pages/{page['id']}/layout").json()
    assert restored["panels"][0]["x"] == 80
    assert restored["panels"][0]["y"] == 100


def test_render_versions_remain_available_after_approval(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    project_id = demo["project"]["id"]
    panel_id = demo["panel_ids"][0]
    history = client.get(f"/panels/{panel_id}/renders").json()
    assert history

    approval = client.post(f"/renders/{history[0]['render']['id']}/approve")

    assert approval.status_code == 200
    versions = client.get(f"/projects/{project_id}/versions").json()
    render_versions = [version for version in versions if version["entity_type"] == "render"]
    assert render_versions
    assert render_versions[0]["asset_ids"]
    assert render_versions[0]["snapshot_json"]["render"]["id"] == history[0]["render"]["id"]


def test_project_checkpoint_captures_key_entities(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    project_id = demo["project"]["id"]

    response = client.post(
        f"/projects/{project_id}/checkpoint",
        json={"label": "Before final polish", "created_by": "test", "reason": "manual_test_checkpoint"},
    )

    assert response.status_code == 201
    versions = response.json()
    entity_types = {version["entity_type"] for version in versions}
    assert {
        "project",
        "page",
        "panel",
        "layout",
        "lettering",
        "story_bible",
        "style_bible",
        "character_card",
    }.issubset(entity_types)
    assert all(version["is_checkpoint"] for version in versions)
    assert all(version["label"] == "Before final polish" for version in versions)


def test_version_diff_reports_structured_changes(client) -> None:
    project = client.post("/projects", json={"name": "Version Diff"}).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 700, "height": 1000}).json()
    first = client.put(f"/pages/{page['id']}/layout", json=page_layout_payload(80, 100)).json()
    second_payload = page_layout_payload(240, 260)
    second_payload["panels"][0]["id"] = first["panels"][0]["id"]
    client.put(f"/pages/{page['id']}/layout", json=second_payload)
    third_payload = page_layout_payload(320, 360)
    third_payload["panels"][0]["id"] = first["panels"][0]["id"]
    client.put(f"/pages/{page['id']}/layout", json=third_payload)

    versions = [
        version
        for version in client.get(f"/projects/{project['id']}/versions").json()
        if version["entity_type"] == "layout" and version["reason"] == "before_page_layout_update"
    ]
    diff = client.get(f"/versions/{versions[1]['id']}/diff/{versions[0]['id']}").json()

    assert diff["changed"]
    assert any(key.endswith(".x") for key in diff["changed"])
