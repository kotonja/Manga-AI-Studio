from collections.abc import Generator

import pytest
from pydantic import ValidationError
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine, select

from manga_api.ai_tasks import AITaskRunner, PromptRegistry, SUPPORTED_TASK_TYPES
from manga_api.config import get_settings
from manga_api.llm import MockLLMProvider
from manga_api.models import AITaskRun, PromptTemplate
from manga_api.schemas import (
    BubblePlanResult,
    CharacterCardsResult,
    ChapterPlanBatchResult,
    CritiqueResult,
    LayoutPlanResult,
    LocationObjectCardsResult,
    PagePlanBatchResult,
    PanelPlanBatchResult,
    PanelPromptResult,
    RepairInvalidJsonResult,
    StoryBibleResult,
    StyleDNAOptionsResult,
    StyleBibleTaskResult,
)


SCHEMAS = {
    "BubblePlanResult": BubblePlanResult,
    "CharacterCardsResult": CharacterCardsResult,
    "ChapterPlanBatchResult": ChapterPlanBatchResult,
    "CritiqueResult": CritiqueResult,
    "LayoutPlanResult": LayoutPlanResult,
    "LocationObjectCardsResult": LocationObjectCardsResult,
    "PagePlanBatchResult": PagePlanBatchResult,
    "PanelPlanBatchResult": PanelPlanBatchResult,
    "PanelPromptResult": PanelPromptResult,
    "RepairInvalidJsonResult": RepairInvalidJsonResult,
    "StoryBibleResult": StoryBibleResult,
    "StyleDNAOptionsResult": StyleDNAOptionsResult,
    "StyleBibleTaskResult": StyleBibleTaskResult,
}


@pytest.fixture()
def session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as test_session:
        yield test_session
    SQLModel.metadata.drop_all(engine)


def test_prompt_registry_loads_all_supported_task_types() -> None:
    templates = PromptRegistry().load_all()
    task_types = {template.task_type for template in templates}
    assert task_types == SUPPORTED_TASK_TYPES
    assert all(template.id for template in templates)
    assert all(template.version for template in templates)
    assert all(template.system_prompt for template in templates)
    assert all(template.user_prompt_template for template in templates)
    assert all(template.output_schema_name in SCHEMAS for template in templates)


def test_every_prompt_returns_valid_json_with_mock_provider(session: Session) -> None:
    registry = PromptRegistry()
    runner = AITaskRunner(session, registry)
    provider = MockLLMProvider()

    for template in registry.load_all():
        schema = SCHEMAS[template.output_schema_name]
        result = runner.run(
            template.task_type,
            sample_inputs_for(template.task_type),
            schema,
            provider,
        )
        assert isinstance(result, schema)

    prompt_rows = session.exec(select(PromptTemplate)).all()
    task_rows = session.exec(select(AITaskRun)).all()
    assert len(prompt_rows) == len(SUPPORTED_TASK_TYPES)
    assert len(task_rows) == len(SUPPORTED_TASK_TYPES)
    assert all(row.status == "succeeded" for row in task_rows)


def test_schemas_reject_bad_outputs() -> None:
    with pytest.raises(ValidationError):
        StoryBibleResult.model_validate({"logline": ""})

    with pytest.raises(ValidationError):
        LayoutPlanResult.model_validate(
            {
                "width": 1000,
                "height": 1500,
                "bleed": 40,
                "safe_margin": 80,
                "reading_direction": "rtl",
                "panels": [
                    {
                        "panel_order": 1,
                        "x": 80,
                        "y": 100,
                        "width": 400,
                        "height": 300,
                        "polygon": [
                            {"x": 80, "y": 100},
                            {"x": 480, "y": 100},
                            {"x": 480, "y": 400},
                            {"x": 80, "y": 400},
                        ],
                    },
                    {
                        "panel_order": 1,
                        "x": 80,
                        "y": 500,
                        "width": 400,
                        "height": 300,
                        "polygon": [
                            {"x": 80, "y": 500},
                            {"x": 480, "y": 500},
                            {"x": 480, "y": 800},
                            {"x": 80, "y": 800},
                        ],
                    },
                ],
            }
        )


def test_ai_task_runner_repairs_invalid_json(session: Session) -> None:
    provider = OneBadOutputProvider()
    result = AITaskRunner(session).run(
        "generate_story_bible",
        sample_inputs_for("generate_story_bible"),
        StoryBibleResult,
        provider,
        max_retries=0,
    )

    assert result.logline
    runs = session.exec(select(AITaskRun).order_by(AITaskRun.created_at.asc())).all()
    assert [run.task_type for run in runs] == ["generate_story_bible", "repair_invalid_json"]
    assert all(run.status == "succeeded" for run in runs)


def test_admin_ai_task_runs_route_is_dev_gated(client, monkeypatch) -> None:
    response = client.get("/admin/ai-task-runs")
    assert response.status_code == 404

    monkeypatch.setenv("ENABLE_DEV_ADMIN", "true")
    get_settings.cache_clear()
    enabled_response = client.get("/admin/ai-task-runs")
    assert enabled_response.status_code == 200
    assert enabled_response.json() == []

    monkeypatch.delenv("ENABLE_DEV_ADMIN", raising=False)
    get_settings.cache_clear()


class OneBadOutputProvider(MockLLMProvider):
    def __init__(self) -> None:
        self.did_fail = False

    def generate_text(self, *args, **kwargs) -> str:
        if kwargs.get("task_type") != "repair_invalid_json" and not self.did_fail:
            self.did_fail = True
            return '{"logline": '
        return super().generate_text(*args, **kwargs)


def sample_inputs_for(task_type: str) -> dict:
    base = {
        "premise": "A lonely swordsman protects a ghost child in a ruined city.",
        "project_name": "Ghost Lantern",
        "target_schema_name": "StoryBibleResult",
        "invalid_json": '{"logline": ',
        "error_message": "Invalid JSON",
    }
    if task_type == "repair_invalid_json":
        return {
            **base,
            "target_schema_json": StoryBibleResult.model_json_schema(),
        }
    return base
