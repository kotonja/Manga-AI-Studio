def create_project_page(client):
    project = client.post("/projects", json={"name": "Layout Test"}).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 1000, "height": 1400}).json()
    return project, page


def panel_payload(order=1, x=100, y=120, width=300, height=280):
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "reading_order": order,
        "prompt": "Panel prompt",
        "polygon": [
            {"x": x, "y": y},
            {"x": x + width, "y": y},
            {"x": x + width, "y": y + height},
            {"x": x, "y": y + height},
        ],
    }


def test_save_and_load_page_layout_preserves_reading_direction(client) -> None:
    _, page = create_project_page(client)

    save_response = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 1000,
            "height": 1400,
            "bleed": 32,
            "safe_margin": 96,
            "reading_direction": "vertical-rl",
            "qa_overlay_enabled": True,
            "panels": [panel_payload(order=1)],
        },
    )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["reading_direction"] == "vertical-rl"
    assert saved["qa_overlay_enabled"] is True
    assert saved["panels"][0]["polygon"][0] == {"x": 100.0, "y": 120.0}

    load_response = client.get(f"/pages/{page['id']}/layout")
    assert load_response.status_code == 200
    loaded = load_response.json()
    assert loaded["reading_direction"] == "vertical-rl"
    assert loaded["panels"][0]["reading_order"] == 1


def test_layout_rejects_panel_outside_page_bounds(client) -> None:
    _, page = create_project_page(client)

    response = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 1000,
            "height": 1400,
            "bleed": 0,
            "safe_margin": 80,
            "reading_direction": "rtl",
            "qa_overlay_enabled": False,
            "panels": [panel_payload(order=1, x=900, y=100, width=200, height=200)],
        },
    )

    assert response.status_code == 422
    assert "inside page bounds" in response.text


def test_layout_rejects_duplicate_panel_order(client) -> None:
    _, page = create_project_page(client)

    response = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 1000,
            "height": 1400,
            "bleed": 0,
            "safe_margin": 80,
            "reading_direction": "ltr",
            "qa_overlay_enabled": False,
            "panels": [
                panel_payload(order=1),
                panel_payload(order=1, x=500, y=100, width=220, height=220),
            ],
        },
    )

    assert response.status_code == 422
    assert "reading order" in response.text


def test_bubble_text_cannot_be_empty_and_can_update(client) -> None:
    _, page = create_project_page(client)
    layout = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 1000,
            "height": 1400,
            "bleed": 0,
            "safe_margin": 80,
            "reading_direction": "rtl",
            "qa_overlay_enabled": False,
            "panels": [panel_payload(order=1)],
        },
    ).json()
    panel_id = layout["panels"][0]["id"]

    empty_response = client.post(
        f"/panels/{panel_id}/bubbles",
        json={"kind": "speech", "x": 100, "y": 100, "width": 240, "height": 120, "text": "   "},
    )
    assert empty_response.status_code == 422

    create_response = client.post(
        f"/panels/{panel_id}/bubbles",
        json={"kind": "speech", "x": 100, "y": 100, "width": 240, "height": 120, "text": "Hello!"},
    )
    assert create_response.status_code == 201
    bubble = create_response.json()

    update_response = client.put(f"/bubbles/{bubble['id']}", json={"text": "Updated line"})
    assert update_response.status_code == 200
    assert update_response.json()["text"] == "Updated line"
