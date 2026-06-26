from manga_api.lettering import fit_text_to_box


def test_text_fitting_shrinks_and_warns_for_long_text() -> None:
    result = fit_text_to_box(
        "This is a very long line of dialogue that needs to wrap and shrink before it can fit inside a small manga bubble.",
        180,
        80,
        font_size=28,
    )

    assert result.font_size < 28
    assert result.lines
    assert result.warning


def test_lettering_generation_stores_bubble_tail_target(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    page_id = demo["page_ids"][0]

    response = client.post(f"/pages/{page_id}/lettering/generate")

    assert response.status_code == 201
    bubbles = response.json()["bubbles"]
    assert bubbles
    assert bubbles[0]["tail_target"]["x"] >= 0
    assert bubbles[0]["tail_target"]["y"] >= 0
    assert bubbles[0]["position"] == {"x": bubbles[0]["x"], "y": bubbles[0]["y"]}
    assert bubbles[0]["size"] == {"width": bubbles[0]["width"], "height": bubbles[0]["height"]}


def test_lettering_svg_export_contains_bubble_text(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    page_id = demo["page_ids"][0]
    lettering = client.post(f"/pages/{page_id}/lettering/generate").json()
    bubble_text = lettering["bubbles"][0]["text"]

    response = client.get(f"/pages/{page_id}/lettering.svg")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert bubble_text in response.text
    assert "<svg" in response.text


def test_lettering_planner_respects_page_bounds(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    page_id = demo["page_ids"][0]
    page = next(page for page in client.get(f"/projects/{demo['project']['id']}").json()["pages"] if page["id"] == page_id)

    response = client.post(f"/pages/{page_id}/lettering/generate")

    assert response.status_code == 201
    lettering = response.json()
    for bubble in lettering["bubbles"]:
        assert bubble["x"] >= 0
        assert bubble["y"] >= 0
        assert bubble["x"] + bubble["width"] <= page["width"]
        assert bubble["y"] + bubble["height"] <= page["height"]
    for element in lettering["sfx"]:
        x = element["position"]["x"]
        y = element["position"]["y"]
        width = element["size"]["width"]
        height = element["size"]["height"]
        assert x >= 0
        assert y >= 0
        assert x + width <= page["width"]
        assert y + height <= page["height"]


def test_sfx_cannot_be_saved_outside_page_bounds(client) -> None:
    demo = client.post("/demo/create-full-project").json()
    page_id = demo["page_ids"][0]
    page = next(page for page in client.get(f"/projects/{demo['project']['id']}").json()["pages"] if page["id"] == page_id)

    response = client.post(
        f"/pages/{page_id}/sfx",
        json={
            "text": "BOOM",
            "position": {"x": page["width"] - 20, "y": 40},
            "size": {"width": 120, "height": 80},
        },
    )

    assert response.status_code == 422
    assert "inside page bounds" in response.json()["detail"]
