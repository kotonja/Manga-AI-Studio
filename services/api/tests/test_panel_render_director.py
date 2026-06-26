def test_panel_render_prompt_includes_required_context(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    panel_id = demo["panel_ids"][0]

    response = client.get(f"/panels/{panel_id}/render-prompts")

    assert response.status_code == 200
    prompts = response.json()
    assert prompts
    prompt = prompts[0]
    context = prompt["structured_context"]
    director = context["panel_render_director"]
    assert prompt["prompt_version"] == "panel-render-director-v1"
    assert "black-and-white original manga panel" in prompt["positive_prompt"]
    assert "bubble-safe" in prompt["positive_prompt"]
    assert "text baked into art" in prompt["negative_prompt"]
    assert director["project_metadata"]["name"] == "Ghost Lantern"
    assert director["style_dna"]
    assert director["story_bible_summary"]["logline"]
    assert director["chapter_summary"]["summary"]
    assert director["scene_summary"]["summary"]
    assert director["panel_story_beat"]
    assert director["composition"]["polygon"]
    assert director["characters"][0]["identity_anchors"]
    assert director["location_anchors"]
    assert director["object_anchors"]


def test_panel_render_history_stores_multiple_attempts(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    panel_id = demo["panel_ids"][0]

    first = client.post(
        f"/panels/{panel_id}/render",
        json={"provider_name": "mock", "render_mode": "storyboard", "seed": 111},
    )
    second = client.post(
        f"/panels/{panel_id}/rerender",
        json={"provider_name": "mock", "render_mode": "draft", "control": "new_seed"},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    history = client.get(f"/panels/{panel_id}/renders")
    assert history.status_code == 200
    items = history.json()
    assert len(items) >= 3
    assert all(item["prompt"] for item in items)
    assert {item["prompt"]["quality_mode"] for item in items} >= {"storyboard", "draft"}


def test_approved_render_is_used_by_compositor(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    page_id = demo["page_ids"][0]
    panel_id = demo["panel_ids"][0]

    client.post(
        f"/panels/{panel_id}/render",
        json={"provider_name": "mock", "render_mode": "storyboard", "seed": 222},
    )
    client.post(
        f"/panels/{panel_id}/rerender",
        json={"provider_name": "mock", "render_mode": "draft", "control": "new_seed"},
    )
    history = client.get(f"/panels/{panel_id}/renders").json()
    approved_item = history[-1]
    approve_response = client.post(f"/renders/{approved_item['render']['id']}/approve")
    assert approve_response.status_code == 200
    assert approve_response.json()["approved"] is True

    compose_response = client.post(f"/pages/{page_id}/compose", json={})
    assert compose_response.status_code == 201
    metadata = compose_response.json()["metadata_json"]
    assert metadata["panel_render_asset_ids"][panel_id] == approved_item["render"]["asset_id"]
    assert metadata["approved_render_asset_ids"][panel_id] == approved_item["render"]["asset_id"]
