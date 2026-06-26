def create_project(client):
    response = client.post("/projects", json={"name": "Lab Project", "description": "Design lab test"})
    assert response.status_code == 201
    return response.json()


def declare_upload_rights(client, project_id):
    response = client.put(
        f"/projects/{project_id}/rights-declaration",
        json={
            "user_confirms_upload_rights": True,
            "user_confirms_no_unlicensed_ip": True,
            "user_confirms_review_required_before_publish": True,
            "notes": "Test user owns or can use uploaded references.",
        },
    )
    assert response.status_code == 200
    return response.json()


def character_payload(name="Nami Vale"):
    return {
        "name": name,
        "aliases": ["Margin Witch"],
        "age_range": "16-18",
        "role": "Protagonist",
        "personality": "Stubborn, inventive, empathetic",
        "face_description": "Round face with expressive brows",
        "hair_description": "Short dark hair with panel-shaped clips",
        "eye_description": "Large bright eyes",
        "body_type": "Small, athletic",
        "outfit_default": "Short jacket, utility skirt, ink pouch",
        "accessories": ["hair clips", "sketchbook"],
        "scars_marks": "Ink stain on right hand",
        "voice_style": "Fast, sincere, a little defiant",
        "forbidden_changes": ["Do not change hair clips"],
        "continuity_rules": ["Ink stain always stays visible"],
    }


def style_payload(name="Kurobay House Style"):
    return {
        "name": name,
        "linework": "Bold silhouettes with fine background detail",
        "screentone": "Sparse, high contrast",
        "hatching": "Angular hatching for tension",
        "black_white_balance": "Heavy blacks in foreground",
        "face_language": "Expressive eyes and brows",
        "anatomy_style": "Stylized but grounded",
        "background_detail": "Dense urban fantasy details",
        "panel_rhythm": "Fast diagonals, calm symmetrical beats",
        "sfx_style": "Hand-drawn block SFX",
        "typography_notes": "Clean dialogue lettering",
        "forbidden_references": ["No photo-realism"],
        "prompt_style_positive": "crisp manga inks, dynamic composition",
        "prompt_style_negative": "muddy anatomy, blurry lines",
    }


def test_character_card_crud_reference_asset_and_mock_sheet(client) -> None:
    project = create_project(client)
    declare_upload_rights(client, project["id"])

    create_response = client.post(f"/projects/{project['id']}/characters", json=character_payload())
    assert create_response.status_code == 201
    character = create_response.json()
    assert character["name"] == "Nami Vale"
    assert character["aliases"] == ["Margin Witch"]

    list_response = client.get(f"/projects/{project['id']}/characters")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.put(f"/characters/{character['id']}", json={"personality": "Brave and impatient"})
    assert update_response.status_code == 200
    assert update_response.json()["personality"] == "Brave and impatient"

    asset_response = client.post(
        f"/characters/{character['id']}/reference-assets",
        json={
            "filename": "nami-front.png",
            "content_type": "image/png",
            "size_bytes": 1234,
            "metadata_json": {"pose": "front"},
        },
    )
    assert asset_response.status_code == 201
    asset = asset_response.json()
    assert asset["character_card_id"] == character["id"]
    assert asset["storage_key"].startswith("characters/")
    assert asset["id"] in client.get(f"/characters/{character['id']}").json()["reference_asset_ids"]
    reference_list = client.get(f"/characters/{character['id']}/reference-assets")
    assert reference_list.status_code == 200
    assert reference_list.json()[0]["id"] == asset["id"]

    sheet_response = client.post(f"/characters/{character['id']}/generate-character-sheet")
    assert sheet_response.status_code == 201
    sheet = sheet_response.json()
    assert sheet["job"]["status"] == "succeeded"
    assert sheet["job"]["job_type"] == "character_sheet"
    assert len(sheet["assets"]) == 4
    assert "joy" in sheet["expression_sheet"]["expressions"]
    updated_character = client.get(f"/characters/{character['id']}").json()
    assert sheet["assets"][0]["id"] in updated_character["reference_asset_ids"]


def test_character_state_crud(client) -> None:
    project = create_project(client)
    character = client.post(f"/projects/{project['id']}/characters", json=character_payload()).json()
    story_response = client.post(f"/projects/{project['id']}/story/generate-bible", json={"premise": "A careful ink witch saves a city."})
    assert story_response.status_code == 201
    chapter_response = client.post(f"/projects/{project['id']}/story/generate-chapter-plan")
    assert chapter_response.status_code == 201
    chapter = chapter_response.json()[0]
    scene = chapter["scenes"][0]
    page = client.post(f"/projects/{project['id']}/pages", json={"width": 900, "height": 1300}).json()

    create_state = client.post(
        f"/characters/{character['id']}/states",
        json={
            "chapter_id": chapter["id"],
            "scene_id": scene["id"],
            "page_id": page["id"],
            "outfit_state": "Ink-proof jacket buttoned high.",
            "injury_state": "No injuries.",
            "emotional_state": "focused",
            "prop_state": "sketchbook in left hand",
            "visibility_notes": "full silhouette visible",
            "continuity_notes": "hair clips remain visible",
        },
    )
    assert create_state.status_code == 201
    state = create_state.json()
    assert state["outfit_state"] == "Ink-proof jacket buttoned high."

    update_state = client.put(f"/character-states/{state['id']}", json={"injury_state": "Small bandage on right hand."})
    assert update_state.status_code == 200
    assert update_state.json()["injury_state"] == "Small bandage on right hand."

    list_states = client.get(f"/characters/{character['id']}/states")
    assert list_states.status_code == 200
    assert list_states.json()[0]["id"] == state["id"]


def test_style_bible_crud_sample_asset_and_active_project_style(client) -> None:
    project = create_project(client)
    declare_upload_rights(client, project["id"])

    create_response = client.post(f"/projects/{project['id']}/style-bibles", json=style_payload())
    assert create_response.status_code == 201
    style = create_response.json()
    assert style["name"] == "Kurobay House Style"
    assert style["linework"].startswith("Bold")

    list_response = client.get(f"/projects/{project['id']}/style-bibles")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    update_response = client.put(f"/style-bibles/{style['id']}", json={"sfx_style": "Jagged ink burst SFX"})
    assert update_response.status_code == 200
    assert update_response.json()["sfx_style"] == "Jagged ink burst SFX"

    sample_response = client.post(
        f"/style-bibles/{style['id']}/sample-assets",
        json={
            "filename": "ink-sample.png",
            "content_type": "image/png",
            "size_bytes": 2048,
            "metadata_json": {"source": "upload"},
        },
    )
    assert sample_response.status_code == 201
    assert sample_response.json()["style_bible_id"] == style["id"]

    active_response = client.put(f"/projects/{project['id']}/active-style", json={"style_bible_id": style["id"]})
    assert active_response.status_code == 200
    assert active_response.json()["id"] == style["id"]

    project_response = client.get(f"/projects/{project['id']}")
    assert project_response.status_code == 200
    assert project_response.json()["active_style_bible_id"] == style["id"]
