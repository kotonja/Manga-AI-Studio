from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel, Field, ValidationError
from sqlmodel import Session, select

from manga_api.models import AITaskRun, PromptTemplate
from manga_api.schemas import RepairInvalidJsonResult

SchemaT = TypeVar("SchemaT", bound=BaseModel)

SUPPORTED_TASK_TYPES = {
    "generate_story_bible",
    "generate_character_cards",
    "generate_location_cards",
    "generate_style_bible",
    "generate_style_dna",
    "generate_chapter_plan",
    "generate_page_plan",
    "generate_panel_plan",
    "generate_layout_plan",
    "generate_panel_prompt",
    "generate_bubble_plan",
    "critique_page",
    "critique_panel",
    "repair_invalid_json",
}


class StructuredProvider(Protocol):
    def generate_structured(
        self,
        schema: type[SchemaT],
        system_prompt: str,
        user_prompt: str,
    ) -> SchemaT:
        """Generate a schema-validated object."""


class TextProvider(Protocol):
    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        task_type: str | None = None,
        schema_name: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        """Generate raw text."""


class PromptTemplateFile(BaseModel):
    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=240)
    version: str = Field(min_length=1, max_length=80)
    task_type: str = Field(min_length=1, max_length=80)
    system_prompt: str = Field(min_length=1)
    user_prompt_template: str = Field(min_length=1)
    output_schema_name: str = Field(min_length=1, max_length=160)
    default_options: dict[str, Any] = Field(default_factory=dict)
    safety_notes: str = ""
    changelog: list[dict[str, Any]] = Field(default_factory=list)


class PromptRegistry:
    def __init__(self, prompt_dir: Path | None = None) -> None:
        self.prompt_dir = prompt_dir or default_prompt_dir()

    def load_all(self) -> list[PromptTemplateFile]:
        if not self.prompt_dir.exists():
            raise FileNotFoundError(f"Prompt registry directory not found: {self.prompt_dir}")
        templates: list[PromptTemplateFile] = []
        for path in sorted(self.prompt_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            template = PromptTemplateFile.model_validate(data)
            if template.task_type not in SUPPORTED_TASK_TYPES:
                raise ValueError(f"Unsupported prompt task_type {template.task_type!r} in {path}")
            templates.append(template)
        if not templates:
            raise ValueError(f"No prompt templates found in {self.prompt_dir}")
        return templates

    def get_latest(self, task_type: str) -> PromptTemplateFile:
        matches = [template for template in self.load_all() if template.task_type == task_type]
        if not matches:
            raise ValueError(f"No prompt template registered for task_type={task_type}")
        return sorted(matches, key=lambda template: (template.version, template.id))[-1]


class AITaskRunner:
    def __init__(self, session: Session, registry: PromptRegistry | None = None) -> None:
        self.session = session
        self.registry = registry or PromptRegistry()

    def run(
        self,
        task_type: str,
        inputs: dict[str, Any],
        schema: type[SchemaT],
        provider: StructuredProvider | TextProvider,
        *,
        max_retries: int = 1,
        allow_repair: bool = True,
    ) -> SchemaT:
        if task_type not in SUPPORTED_TASK_TYPES:
            raise ValueError(f"Unsupported AI task type: {task_type}")

        template = self.registry.get_latest(task_type)
        prompt_template = self._upsert_prompt_template(template)
        schema_name = schema.__name__
        schema_json = schema_json_for_prompt(schema)
        render_values = {
            **inputs,
            "inputs_json": pretty_json(inputs),
            "schema_json": schema_json,
            "schema_name": schema_name,
            "output_schema_name": template.output_schema_name,
        }
        system_prompt = render_prompt(template.system_prompt, render_values)
        user_prompt = render_prompt(template.user_prompt_template, render_values)
        provider_name = provider_name_for(provider)
        model_name = model_name_for(provider)

        task_run = AITaskRun(
            prompt_template_id=prompt_template.id,
            task_type=task_type,
            status="running",
            provider=provider_name,
            model=model_name,
            schema_name=schema_name,
            schema_version=schema_version(schema),
            raw_input=to_jsonable(
                {
                    "inputs": inputs,
                    "template": template.model_dump(),
                    "rendered_system_prompt": system_prompt,
                    "rendered_user_prompt": user_prompt,
                }
            ),
        )
        self.session.add(task_run)
        self.session.commit()
        self.session.refresh(task_run)

        raw_outputs: list[str] = []
        validation_errors: list[str] = []
        attempts = max(1, max_retries + 1)
        prompt_for_attempt = user_prompt

        try:
            for attempt in range(1, attempts + 1):
                raw_output = call_provider_text(
                    provider,
                    schema,
                    system_prompt,
                    prompt_for_attempt,
                    task_type=task_type,
                    schema_name=schema_name,
                    options=template.default_options,
                )
                raw_outputs.append(raw_output)
                try:
                    parsed_output = parse_and_validate(raw_output, schema)
                    return self._succeed(task_run, parsed_output, raw_outputs, attempt, provider)
                except (json.JSONDecodeError, ValidationError, ValueError) as exc:
                    validation_errors.append(str(exc))
                    prompt_for_attempt = (
                        f"{user_prompt}\n\nPrevious output was invalid for {schema_name}.\n"
                        f"Validation error:\n{str(exc)[:3000]}\nReturn corrected JSON only."
                    )

            if allow_repair:
                repaired = self.run(
                    "repair_invalid_json",
                    {
                        "invalid_json": raw_outputs[-1] if raw_outputs else "",
                        "target_schema_name": schema_name,
                        "target_schema_json": schema_json,
                        "error_message": validation_errors[-1] if validation_errors else "Unknown validation error",
                    },
                    RepairInvalidJsonResult,
                    provider,
                    max_retries=0,
                    allow_repair=False,
                )
                parsed_output = schema.model_validate(repaired.repaired_json)
                return self._succeed(
                    task_run,
                    parsed_output,
                    raw_outputs,
                    len(raw_outputs),
                    provider,
                    extra_raw_input={"repair_task": True, "repair_output": repaired.model_dump()},
                )

            raise ValueError(validation_errors[-1] if validation_errors else "AI task returned invalid output")
        except Exception as exc:
            task_run.status = "failed"
            task_run.raw_output = "\n\n--- attempt ---\n\n".join(raw_outputs) if raw_outputs else None
            task_run.error_message = str(exc)[:8000]
            task_run.attempt_count = len(raw_outputs)
            task_run.token_metadata = token_metadata_for(provider)
            task_run.cost_metadata = cost_metadata_for(provider)
            self.session.add(task_run)
            self.session.commit()
            raise

    def _upsert_prompt_template(self, template: PromptTemplateFile) -> PromptTemplate:
        row = self.session.get(PromptTemplate, template.id)
        if row is None:
            row = PromptTemplate(id=template.id)
        row.name = template.name
        row.version = template.version
        row.task_type = template.task_type
        row.system_prompt = template.system_prompt
        row.user_prompt_template = template.user_prompt_template
        row.output_schema_name = template.output_schema_name
        row.default_options = template.default_options
        row.safety_notes = template.safety_notes
        row.changelog = template.changelog
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return row

    def _succeed(
        self,
        task_run: AITaskRun,
        parsed_output: SchemaT,
        raw_outputs: list[str],
        attempt_count: int,
        provider: StructuredProvider | TextProvider,
        *,
        extra_raw_input: dict[str, Any] | None = None,
    ) -> SchemaT:
        task_run.status = "succeeded"
        task_run.raw_output = "\n\n--- attempt ---\n\n".join(raw_outputs)
        task_run.parsed_output = to_jsonable(parsed_output.model_dump(mode="json"))
        task_run.error_message = None
        task_run.attempt_count = attempt_count
        task_run.token_metadata = token_metadata_for(provider)
        task_run.cost_metadata = cost_metadata_for(provider)
        if extra_raw_input:
            task_run.raw_input = {**task_run.raw_input, **to_jsonable(extra_raw_input)}
        self.session.add(task_run)
        self.session.commit()
        return parsed_output


def default_prompt_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "app" / "prompts"


def render_prompt(template: str, values: dict[str, Any]) -> str:
    pattern = re.compile(r"{{\s*([a-zA-Z0-9_.-]+)\s*}}")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = lookup_value(values, key)
        if isinstance(value, str):
            return value
        return pretty_json(value)

    return pattern.sub(replace, template)


def lookup_value(values: dict[str, Any], key: str) -> Any:
    current: Any = values
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    return current


def call_provider_text(
    provider: StructuredProvider | TextProvider,
    schema: type[SchemaT],
    system_prompt: str,
    user_prompt: str,
    *,
    task_type: str,
    schema_name: str,
    options: dict[str, Any],
) -> str:
    generate_text = getattr(provider, "generate_text", None)
    if callable(generate_text):
        return str(
            generate_text(
                system_prompt,
                user_prompt,
                task_type=task_type,
                schema_name=schema_name,
                options=options,
            )
        )
    structured = provider.generate_structured(schema, system_prompt, user_prompt)
    return structured.model_dump_json()


def parse_and_validate(raw_output: str, schema: type[SchemaT]) -> SchemaT:
    parsed_json = json.loads(extract_json(raw_output))
    return schema.model_validate(parsed_json)


def extract_json(raw_output: str) -> str:
    stripped = raw_output.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    if stripped.startswith("{") or stripped.startswith("["):
        return stripped
    starts = [index for index in [stripped.find("{"), stripped.find("[")] if index >= 0]
    if not starts:
        raise ValueError("AI output did not contain JSON")
    start = min(starts)
    end = max(stripped.rfind("}"), stripped.rfind("]"))
    if end <= start:
        raise ValueError("AI output JSON was incomplete")
    return stripped[start : end + 1]


def schema_json_for_prompt(schema: type[BaseModel]) -> str:
    return pretty_json(schema.model_json_schema())


def schema_version(schema: type[BaseModel]) -> str:
    return str(getattr(schema, "schema_version", "1"))


def provider_name_for(provider: Any) -> str:
    return str(getattr(provider, "name", provider.__class__.__name__))


def model_name_for(provider: Any) -> str | None:
    model = getattr(provider, "model", None) or getattr(provider, "model_name", None)
    return str(model) if model is not None else None


def token_metadata_for(provider: Any) -> dict[str, Any]:
    return to_jsonable(getattr(provider, "last_token_metadata", {}))


def cost_metadata_for(provider: Any) -> dict[str, Any]:
    return to_jsonable(getattr(provider, "last_cost_metadata", {}))


def pretty_json(value: Any) -> str:
    return json.dumps(to_jsonable(value), indent=2, sort_keys=True, ensure_ascii=True)


def to_jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=json_default, ensure_ascii=True))


def json_default(value: Any) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def list_recent_ai_task_runs(session: Session, limit: int = 50) -> list[AITaskRun]:
    safe_limit = max(1, min(limit, 200))
    return list(
        session.exec(
            select(AITaskRun)
            .order_by(AITaskRun.created_at.desc(), AITaskRun.id.desc())
            .limit(safe_limit)
        ).all()
    )
