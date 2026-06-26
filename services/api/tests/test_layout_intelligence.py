def create_story_page(client):
    project = client.post("/projects", json={"name": "Layout Intelligence"}).json()
    bible_response = client.post(
        f"/projects/{project['id']}/story/generate-bible",
        json={"premise": "A lonely swordsman protects a ghost child in a ruined city."},
    )
    assert bible_response.status_code == 201
    chapter_response = client.post(f"/projects/{project['id']}/story/generate-chapter-plan")
    assert chapter_response.status_code == 201
    chapter = chapter_response.json()[0]
    page_plans_response = client.post(f"/chapters/{chapter['id']}/story/generate-page-plans")
    assert page_plans_response.status_code == 201
    page = client.post(f"/projects/{project['id']}/pages", json={"page_number": 1, "width": 1000, "height": 1400}).json()
    return project, page


def panel_payload(order=1, x=100, y=100, width=320, height=300):
    return {
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "reading_order": order,
        "prompt": "Locked panel",
        "polygon": [
            {"x": x, "y": y},
            {"x": x + width, "y": y},
            {"x": x + width, "y": y + height},
            {"x": x, "y": y + height},
        ],
    }


def test_generate_rtl_layout_orders_from_right_to_left(client) -> None:
    _, page = create_story_page(client)

    response = client.post(
        f"/pages/{page['id']}/layout/suggest",
        json={"page_type": "standard", "reading_direction": "rtl", "safe_margin": 80, "min_gutter": 12},
    )

    assert response.status_code == 200
    suggestion = response.json()
    panels = suggestion["panels"]
    assert suggestion["reading_direction"] == "rtl"
    assert len(panels) == 2
    assert panels[0]["reading_order"] == 1
    assert panels[0]["x"] > panels[1]["x"]
    assert panels[0]["x"] + panels[0]["width"] <= suggestion["width"]


def test_generate_splash_layout_has_one_dominant_panel(client) -> None:
    _, page = create_story_page(client)

    response = client.post(
        f"/pages/{page['id']}/layout/suggest",
        json={"page_type": "splash", "reading_direction": "ltr", "safe_margin": 60},
    )

    assert response.status_code == 200
    suggestion = response.json()
    assert suggestion["page_type"] == "splash"
    assert len(suggestion["panels"]) == 1
    panel = suggestion["panels"][0]
    available_area = (suggestion["width"] - suggestion["safe_margin"] * 2) * (
        suggestion["height"] - suggestion["safe_margin"] * 2
    )
    assert (panel["width"] * panel["height"]) / available_area > 0.9


def test_generate_dialogue_layout_reserves_bubble_slots(client) -> None:
    _, page = create_story_page(client)

    response = client.post(
        f"/pages/{page['id']}/layout/suggest",
        json={"page_type": "dialogue_scene", "reading_direction": "ltr", "safe_margin": 80},
    )

    assert response.status_code == 200
    suggestion = response.json()
    assert suggestion["page_type"] == "dialogue_scene"
    assert all(panel["bubble_slots"] for panel in suggestion["panels"])
    assert suggestion["validation_issues"] == []


def test_locked_panels_remain_unchanged_when_suggesting_layout(client) -> None:
    _, page = create_story_page(client)
    saved = client.put(
        f"/pages/{page['id']}/layout",
        json={
            "width": 1000,
            "height": 1400,
            "bleed": 0,
            "safe_margin": 80,
            "reading_direction": "rtl",
            "qa_overlay_enabled": False,
            "panels": [panel_payload(order=1, x=96, y=112, width=340, height=310)],
        },
    ).json()
    locked_panel = saved["panels"][0]

    response = client.post(
        f"/pages/{page['id']}/layout/suggest",
        json={
            "page_type": "standard",
            "reading_direction": "rtl",
            "locked_panel_ids": [locked_panel["id"]],
            "safe_margin": 80,
        },
    )

    assert response.status_code == 200
    suggested_locked = next(panel for panel in response.json()["panels"] if panel["id"] == locked_panel["id"])
    assert suggested_locked["locked"] is True
    assert suggested_locked["x"] == locked_panel["x"]
    assert suggested_locked["y"] == locked_panel["y"]
    assert suggested_locked["width"] == locked_panel["width"]
    assert suggested_locked["height"] == locked_panel["height"]


def test_invalid_overlapping_layout_is_rejected(client) -> None:
    _, page = create_story_page(client)

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
                panel_payload(order=1, x=100, y=100, width=360, height=300),
                panel_payload(order=2, x=320, y=180, width=360, height=300),
            ],
        },
    )

    assert response.status_code == 422
    assert "overlaps" in response.text


def test_project_layout_template_crud_and_suggest(client) -> None:
    project, page = create_story_page(client)
    template_response = client.post(
        f"/projects/{project['id']}/layout-templates",
        json={
            "name": "Right Lead Dialogue",
            "page_type": "dialogue_scene",
            "panel_count": 2,
            "reading_direction": "rtl",
            "emotional_use": "Tense protected conversation",
            "action_level": "low",
            "density": "medium",
            "layout_json": {
                "panels": [
                    {"panel_order": 1, "x": 0.52, "y": 0, "width": 0.48, "height": 1},
                    {"panel_order": 2, "x": 0, "y": 0, "width": 0.48, "height": 1},
                ]
            },
            "notes": "Normalized coordinates inside the safe area.",
        },
    )
    assert template_response.status_code == 201
    template = template_response.json()

    list_response = client.get(f"/projects/{project['id']}/layout-templates")
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == template["id"]

    suggest_response = client.post(
        f"/pages/{page['id']}/layout/suggest",
        json={"template_id": template["id"], "page_type": "dialogue_scene", "reading_direction": "rtl"},
    )
    assert suggest_response.status_code == 200
    panels = suggest_response.json()["panels"]
    assert panels[0]["x"] > panels[1]["x"]
