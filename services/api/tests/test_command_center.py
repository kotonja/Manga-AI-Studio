from __future__ import annotations


def create_command_fixture(client):
    project = client.post(
        "/projects",
        json={"name": "Command Center Test", "description": "Commandable manga project."},
    ).json()
    page = client.post(f"/projects/{project['id']}/pages", json={"page_number": 3, "width": 1000, "height": 1500}).json()
    panel = client.post(
        f"/pages/{page['id']}/panels",
        json={"x": 80, "y": 120, "width": 620, "height": 520, "reading_order": 2, "prompt": "Quiet standoff."},
    ).json()
    bubble = client.post(
        f"/panels/{panel['id']}/bubbles",
        json={
            "kind": "speech",
            "x": 120,
            "y": 260,
            "width": 280,
            "height": 120,
            "text": "I cannot keep running from this ruined city forever.",
        },
    ).json()
    return project, page, panel, bubble


def command_payload(project_id: str, scope_type: str, scope_id: str, command: str, confirmed: bool | None = None):
    payload = {
        "project_id": project_id,
        "scope": {"type": scope_type, "id": scope_id},
        "command": command,
    }
    if confirmed is not None:
        payload["confirmed"] = confirmed
    return payload


def test_interpret_page_command(client) -> None:
    project, page, _panel, _bubble = create_command_fixture(client)

    response = client.post(
        "/commands/interpret",
        json=command_payload(project["id"], "page", page["id"], "Make page 3 more dramatic."),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["intent"] == "revise_page_direction"
    assert result["target_type"] == "page"
    assert result["target_id"] == page["id"]
    assert any(action["action_type"] == "suggest_layout" for action in result["proposed_actions"])
    assert result["requires_confirmation"] is False


def test_interpret_panel_command(client) -> None:
    project, page, panel, _bubble = create_command_fixture(client)

    response = client.post(
        "/commands/interpret",
        json=command_payload(project["id"], "page", page["id"], "Regenerate panel 2 with a low-angle shot."),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["intent"] == "rerender_panel"
    assert result["target_type"] == "panel"
    assert result["target_id"] == panel["id"]
    action_types = [action["action_type"] for action in result["proposed_actions"]]
    assert "update_panel_prompt" in action_types
    assert "rerender_panel" in action_types


def test_interpret_lettering_command(client) -> None:
    project, _page, _panel, bubble = create_command_fixture(client)

    response = client.post(
        "/commands/interpret",
        json=command_payload(project["id"], "bubble", bubble["id"], "Move this bubble away from the face."),
    )

    assert response.status_code == 201
    result = response.json()
    assert result["intent"] == "move_lettering"
    assert result["target_type"] == "bubble"
    assert result["target_id"] == bubble["id"]
    assert result["proposed_actions"][0]["action_type"] == "move_bubble"
    assert result["risk_level"] == "low"


def test_execute_safe_bubble_move_creates_version_snapshot(client) -> None:
    project, page, _panel, bubble = create_command_fixture(client)
    before_versions = client.get(f"/projects/{project['id']}/versions").json()

    response = client.post(
        "/commands/execute",
        json=command_payload(project["id"], "bubble", bubble["id"], "Move this bubble away from the face.", confirmed=False),
    )

    assert response.status_code == 202
    result = response.json()
    assert result["status"] == "executed"
    assert result["executed_actions"][0]["action_type"] == "move_bubble"
    assert result["version_ids"]

    layout = client.get(f"/pages/{page['id']}/layout").json()
    moved = layout["panels"][0]["bubbles"][0]
    assert moved["id"] == bubble["id"]
    assert (moved["x"], moved["y"]) != (bubble["x"], bubble["y"])

    after_versions = client.get(f"/projects/{project['id']}/versions").json()
    assert len(after_versions) > len(before_versions)
    assert any(version["entity_type"] == "lettering" for version in after_versions)


def test_risky_command_requires_confirmation(client) -> None:
    project, page, _panel, _bubble = create_command_fixture(client)

    response = client.post(
        "/commands/execute",
        json=command_payload(project["id"], "page", page["id"], "Delete this page.", confirmed=False),
    )

    assert response.status_code == 202
    result = response.json()
    assert result["status"] == "blocked"
    assert result["requires_confirmation"] is True
    assert result["risk_level"] == "high"

    project_detail = client.get(f"/projects/{project['id']}").json()
    assert [existing_page["id"] for existing_page in project_detail["pages"]] == [page["id"]]
