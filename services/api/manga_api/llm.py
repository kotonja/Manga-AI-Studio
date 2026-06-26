from __future__ import annotations

import json
import re
from typing import Protocol, TypeVar

from pydantic import BaseModel

from manga_api.config import get_settings
from manga_api.schemas import (
    ChapterPlanBatchResult,
    PagePlanBatchResult,
    StoryBibleResult,
)

SchemaT = TypeVar("SchemaT", bound=BaseModel)


class LLMProvider(Protocol):
    def generate_structured(
        self,
        schema: type[SchemaT],
        system_prompt: str,
        user_prompt: str,
    ) -> SchemaT:
        """Generate a JSON-compatible object validated by the supplied schema."""


class MockLLMProvider:
    name = "mock"
    model = "mock-llm-v1"

    def generate_structured(
        self,
        schema: type[SchemaT],
        system_prompt: str,
        user_prompt: str,
    ) -> SchemaT:
        raw = self.generate_text(system_prompt, user_prompt, schema_name=schema.__name__)
        return schema.model_validate(json.loads(raw))

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        task_type: str | None = None,
        schema_name: str | None = None,
        options: dict | None = None,
    ) -> str:
        payload = _mock_ai_task_payload(task_type=task_type, schema_name=schema_name, user_prompt=user_prompt)
        return json.dumps(payload, ensure_ascii=True)


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model

    def generate_structured(
        self,
        schema: type[SchemaT],
        system_prompt: str,
        user_prompt: str,
    ) -> SchemaT:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required when MODEL_PROVIDER=openai")
        raise NotImplementedError("OpenAI structured generation is intentionally stubbed for this milestone")

    def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        task_type: str | None = None,
        schema_name: str | None = None,
        options: dict | None = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required when MODEL_PROVIDER=openai")
        raise NotImplementedError("OpenAI text generation is intentionally stubbed for this milestone")


def get_llm_provider() -> LLMProvider:
    provider = get_settings().model_provider.lower()
    if provider == "mock":
        return MockLLMProvider()
    if provider == "openai":
        return OpenAIProvider()
    raise ValueError(f"Unsupported MODEL_PROVIDER: {provider}")


def _mock_ai_task_payload(task_type: str | None, schema_name: str | None, user_prompt: str) -> dict:
    if task_type == "repair_invalid_json":
        target_schema = _extract_target_schema_name(user_prompt)
        return {
            "repaired_json": _mock_payload_for_schema(target_schema),
            "notes": f"Repaired invalid JSON for {target_schema}.",
        }
    if task_type == "generate_story_bible" or schema_name == "StoryBibleResult":
        return _mock_story_bible()
    if task_type == "generate_chapter_plan" or schema_name == "ChapterPlanBatchResult":
        return _mock_chapter_plan()
    if task_type == "generate_page_plan" or schema_name == "PagePlanBatchResult":
        return _mock_page_plans()
    if task_type == "generate_panel_plan" or schema_name == "PanelPlanBatchResult":
        return {"panels": _mock_page_plans()["pages"][0]["panels"]}
    if task_type == "generate_character_cards" or schema_name == "CharacterCardsResult":
        return _mock_character_cards()
    if task_type == "generate_location_cards" or schema_name == "LocationObjectCardsResult":
        story = _mock_story_bible()
        return {"locations": story["locations"], "key_objects": story["key_objects"]}
    if task_type == "generate_style_bible" or schema_name == "StyleBibleTaskResult":
        return _mock_style_bible_task()
    if task_type == "generate_style_dna" or schema_name == "StyleDNAOptionsResult":
        return _mock_style_dna_options()
    if task_type == "generate_layout_plan" or schema_name == "LayoutPlanResult":
        return _mock_layout_plan()
    if task_type == "generate_panel_prompt" or schema_name == "PanelPromptResult":
        return {
            "prompt": "Black-and-white manga panel, clean linework, dramatic rooftop perspective, readable silhouettes.",
            "negative_prompt": "muddy anatomy, unreadable text, blank background",
            "references": [],
            "options": {"seed": 4242},
        }
    if task_type == "generate_bubble_plan" or schema_name == "BubblePlanResult":
        return {
            "bubbles": [
                {
                    "panel_order": 1,
                    "kind": "narration",
                    "text": "Kurobay always looked unfinished from above.",
                    "x": 120,
                    "y": 120,
                    "width": 420,
                    "height": 100,
                },
                {
                    "panel_order": 2,
                    "kind": "speech",
                    "text": "That was not in the morning sketch.",
                    "x": 640,
                    "y": 780,
                    "width": 360,
                    "height": 140,
                },
            ]
        }
    if task_type in {"critique_page", "critique_panel"} or schema_name == "CritiqueResult":
        return {
            "overall_score": 88,
            "scores": {"composition": 90, "continuity": 86, "lettering": 88},
            "issues": [
                {
                    "id": "mock-issue-1",
                    "code": "mock_minor_contrast",
                    "severity": "info",
                    "message": "Increase contrast around the emotional focal point.",
                    "target_type": "page" if task_type == "critique_page" else "panel",
                    "target_id": None,
                    "panel_id": None,
                    "bubble_id": None,
                    "blocking": False,
                    "details": {"provider": "mock"},
                }
            ],
            "recommendations": [
                {
                    "id": "mock-rec-1",
                    "message": "Keep the protagonist silhouette consistent in the next pass.",
                    "target_type": "page" if task_type == "critique_page" else "panel",
                    "target_id": None,
                    "details": {},
                }
            ],
            "blocking": False,
        }
    raise ValueError(f"Unsupported mock task/schema: task_type={task_type}, schema_name={schema_name}")


def _mock_payload_for_schema(schema_name: str) -> dict:
    return _mock_ai_task_payload(task_type=None, schema_name=schema_name, user_prompt="")


def _extract_target_schema_name(user_prompt: str) -> str:
    match = re.search(r'"target_schema_name"\s*:\s*"([^"]+)"', user_prompt)
    return match.group(1) if match else "StoryBibleResult"


def _mock_character_cards() -> dict:
    return {
        "characters": [
            {
                "name": "Nami Vale",
                "aliases": ["Margin Artist"],
                "age_range": "teen",
                "role": "Protagonist",
                "personality": "Inventive, stubborn, empathetic, and easily pulled toward unfinished mysteries.",
                "face_description": "Expressive round face with determined brows.",
                "hair_description": "Short dark hair pinned by panel-shaped clips.",
                "eye_description": "Bright eyes with ink-like highlights.",
                "body_type": "Compact, agile build.",
                "outfit_default": "Short jacket, sketch satchel, sturdy rooftop boots.",
                "accessories": ["panel hair clips", "margin sketchbook"],
                "scars_marks": "Ink stains on fingers.",
                "voice_style": "Fast, candid, emotionally direct.",
                "forbidden_changes": ["Do not remove panel-shaped hair clips."],
                "continuity_rules": ["Ink-stained fingers remain visible in close-ups."],
            },
            {
                "name": "Jun Pike",
                "aliases": ["Rooftop Courier"],
                "age_range": "young adult",
                "role": "Tactician",
                "personality": "Calm, observant, dryly funny, and loyal once trust is earned.",
                "face_description": "Angular face with watchful eyes.",
                "hair_description": "Wind-swept hair tucked behind one ear.",
                "eye_description": "Narrow eyes behind angular glasses.",
                "body_type": "Lean runner build.",
                "outfit_default": "Courier jacket, scarf, messenger bag.",
                "accessories": ["glasses", "messenger bag"],
                "scars_marks": "Small chin scar.",
                "voice_style": "Dry, precise, understated.",
                "forbidden_changes": ["Do not remove glasses."],
                "continuity_rules": ["Messenger bag stays on left shoulder during action."],
            },
        ]
    }


def _mock_style_bible_task() -> dict:
    return {
        "name": "Kurobay Ink Draft",
        **_mock_style_dna_options()["options"][0],
        "linework": "Bold foreground silhouettes with fine architectural hatching.",
        "screentone": "Moderate screentone for night markets and rooftop shadows.",
        "hatching": "Directional hatching for motion and emotional pressure.",
        "black_white_balance": "High-contrast figures against detailed but readable backgrounds.",
        "face_language": "Large readable eyes, restrained mouth shapes, strong brow acting.",
        "anatomy_style": "Grounded action manga proportions.",
        "background_detail": "Dense city detail with clear landmarks.",
        "panel_rhythm": "Fast diagonals for action, quiet symmetrical panels for choices.",
        "sfx_style": "Hand-drawn ink effects integrated into panel motion.",
        "typography_notes": "Clean dialogue balloons and rough-edged sketchbook narration.",
        "forbidden_references": ["photorealism", "muddy grayscale"],
        "prompt_style_positive": "crisp black-and-white manga, readable silhouettes, kinetic gutters",
        "prompt_style_negative": "muddy anatomy, blank backgrounds, unreadable lettering",
    }


def _mock_style_dna_options() -> dict:
    base_options = [
        {
            "style_name": "Raincut Lantern Noir",
            "style_intent": "A melancholic original supernatural action style built around wet silhouettes, ghost-light contrast, and restrained facial acting.",
            "line_weight": "Medium-heavy outer contours with thin interior details for faces and props.",
            "line_variation": "Slow calm scenes use even lines; danger scenes use snapped pressure changes and broken edges.",
            "line_texture": "Dry-brush breaks on ruins, clean smooth strokes on eyes and lantern flame.",
            "face_shape_language": "Long tired faces for adults, small rounded ghost-child shapes for innocence.",
            "eye_design_language": "Dark almond eyes with tiny white value anchors; ghost eyes use reflected lantern flecks.",
            "nose_mouth_simplification": "Minimal wedge noses and narrow mouths, saved expression shifts for brows and eyelids.",
            "anatomy_proportions": "Grounded lean figures with slightly elongated limbs for quiet tension.",
            "hair_rendering": "Grouped black hair masses with a few wet strand cuts at silhouette edges.",
            "clothing_fold_style": "Large angular coat folds with sparse detail inside shadow masses.",
            "background_density": "Dense establishing shots, simplified action backgrounds with one repeated landmark.",
            "architecture_detail": "Broken signage, cracked shrine geometry, hanging cables, and repeatable clocktower shapes.",
            "shadow_strategy": "Deep black foregrounds, ghost-lit rim highlights, and white rain gaps.",
            "screentone_strategy": "Soft gray rain sheets and low-density rubble texture only where depth is needed.",
            "hatching_strategy": "Short directional hatch bursts around fear, impact, and sword draws.",
            "black_fill_ratio": "45 percent black in tense panels, 25 percent in quiet emotional panels.",
            "speedline_style": "Sparse blade-following arcs instead of dense radial bursts.",
            "impact_frame_style": "Thin black impact frames with chipped corners.",
            "panel_border_style": "Clean black borders, slightly thicker during threat beats.",
            "gutter_style": "Wide white gutters for silence, narrow gutters for chase compression.",
            "sfx_shape_language": "Cracked brush shapes that lean with the motion vector.",
            "bubble_style": "Round quiet speech bubbles and rectangular narration with rain-cut corners.",
            "typography_notes": "Compact all-caps dialogue with generous interior bubble padding.",
            "emotional_visual_rules": [
                "Isolation uses large negative space above the character.",
                "Protection beats place the guardian silhouette between threat and child.",
            ],
            "positive_prompt_fragments": [
                "original black-and-white supernatural manga",
                "wet ink silhouettes",
                "ghost-light rim contrast",
                "ruined city landmarks",
            ],
            "negative_prompt_fragments": [
                "artist imitation",
                "franchise resemblance",
                "muddy gray values",
                "overcrowded facial detail",
            ],
            "forbidden_artist_references": [],
            "forbidden_franchise_references": [],
            "preview_prompt": "Original manga sample panel: a lonely swordsman under rain shields a small ghost child near a broken clocktower, wet black silhouettes, ghost-light rim contrast, wide white gutters.",
        },
        {
            "style_name": "Ash Petal Action",
            "style_intent": "A sharp original adventure style where ash, petals, and blade motion define emotional rhythm.",
            "line_weight": "Light interior contour with bold action silhouettes.",
            "line_variation": "Elastic line pressure on motion, calm uniform line on dialogue panels.",
            "line_texture": "Clean faces, grainy ash on backgrounds, feathered sword arcs.",
            "face_shape_language": "Soft triangular faces with clear brow shapes and expressive cheek planes.",
            "eye_design_language": "Large angular eyes with heavy top lashes and minimal lower detail.",
            "nose_mouth_simplification": "Tiny bridge marks and single-stroke mouths.",
            "anatomy_proportions": "Slightly heroic limbs and compact torsos for dynamic poses.",
            "hair_rendering": "Layered hair chunks with white cut-ins for motion.",
            "clothing_fold_style": "Ribbon-like folds that track movement direction.",
            "background_density": "Medium density, with ash clouds replacing detail during combat.",
            "architecture_detail": "Vertical ruins, split gates, and repeated lantern posts.",
            "shadow_strategy": "Alternating white figures on black ash and black figures on white rain.",
            "screentone_strategy": "Low-opacity ash tone behind characters only.",
            "hatching_strategy": "Curved hatching following blade paths.",
            "black_fill_ratio": "35 percent average black with punctuated full-black impact silhouettes.",
            "speedline_style": "Curved petal-like speedlines crossing behind the action.",
            "impact_frame_style": "White flash panels with black debris flecks.",
            "panel_border_style": "Thin borders that break at motion exits.",
            "gutter_style": "Clean white gutters with occasional ash flecks crossing panel edges.",
            "sfx_shape_language": "Brushy petal fragments around impact lettering.",
            "bubble_style": "Simple oval dialogue, small square whispers.",
            "typography_notes": "Lightweight dialogue with heavier SFX strokes.",
            "emotional_visual_rules": [
                "Fear compresses characters low in the frame.",
                "Resolve clears background ash around the face.",
            ],
            "positive_prompt_fragments": [
                "original ash-and-petal manga action",
                "bold readable silhouettes",
                "curved speedline rhythm",
                "clean expressive faces",
            ],
            "negative_prompt_fragments": ["direct artist reference", "franchise likeness", "busy unreadable action"],
            "forbidden_artist_references": [],
            "forbidden_franchise_references": [],
            "preview_prompt": "Original manga sample panel: a sword arc scatters ash petals through a ruined avenue while a ghost lantern glows behind clean expressive faces.",
        },
        {
            "style_name": "Clockwork Ruin Elegy",
            "style_intent": "An original quiet-drama manga style combining precise ruined architecture with sparse, vulnerable character acting.",
            "line_weight": "Thin precise architecture lines with heavier character silhouette locks.",
            "line_variation": "Little line pressure in quiet beats, sudden heavy lines at supernatural reveals.",
            "line_texture": "Architectural cross-grain, smooth skin contours, dotted rain residue.",
            "face_shape_language": "Small mouths, still cheeks, expressive eye spacing.",
            "eye_design_language": "Narrow reflective eyes with simple value blocks.",
            "nose_mouth_simplification": "Short nose ticks and small horizontal mouths.",
            "anatomy_proportions": "Naturalistic bodies with slight manga elongation in hands and coats.",
            "hair_rendering": "Flat black hair groups with controlled white highlights.",
            "clothing_fold_style": "Measured vertical folds and weighty hems.",
            "background_density": "High density in establishing panels, low density in emotional close-ups.",
            "architecture_detail": "Clock gears, cracked tiles, old transit rails, and collapsed eaves.",
            "shadow_strategy": "Architectural shadows form frames around character faces.",
            "screentone_strategy": "Fine mechanical texture tones on ruins, clean whites on ghost elements.",
            "hatching_strategy": "Thin technical hatching for stone and metal.",
            "black_fill_ratio": "30 percent average black, rising to 55 percent in interior ruins.",
            "speedline_style": "Rare, straight mechanical streaks for sudden motion.",
            "impact_frame_style": "Rigid rectangular shock panels with offset inner borders.",
            "panel_border_style": "Precise even borders.",
            "gutter_style": "Quiet wide gutters with strong page breathing.",
            "sfx_shape_language": "Angular mechanical SFX shapes.",
            "bubble_style": "Small restrained bubbles and caption boxes aligned to architecture.",
            "typography_notes": "Quiet, narrow lettering with strong contrast against white bubbles.",
            "emotional_visual_rules": [
                "Loneliness is shown with repeated empty architecture.",
                "Connection reduces background detail and increases eye reflections.",
            ],
            "positive_prompt_fragments": [
                "original precise ruin manga",
                "technical hatching",
                "quiet emotional framing",
                "clockwork architectural motifs",
            ],
            "negative_prompt_fragments": ["artist clone", "franchise design", "loose painterly color"],
            "forbidden_artist_references": [],
            "forbidden_franchise_references": [],
            "preview_prompt": "Original manga sample panel: precise clockwork ruins frame a swordsman and ghost child in quiet rain, technical hatching and restrained expression.",
        },
    ]
    return {"options": base_options}


def _mock_layout_plan() -> dict:
    return {
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
                "width": 840,
                "height": 560,
                "polygon": [
                    {"x": 80, "y": 100},
                    {"x": 920, "y": 100},
                    {"x": 920, "y": 660},
                    {"x": 80, "y": 660},
                ],
                "visual_notes": "Wide rooftop establishing panel.",
            },
            {
                "panel_order": 2,
                "x": 80,
                "y": 760,
                "width": 840,
                "height": 600,
                "polygon": [
                    {"x": 80, "y": 760},
                    {"x": 920, "y": 760},
                    {"x": 920, "y": 1360},
                    {"x": 80, "y": 1360},
                ],
                "visual_notes": "Medium reaction panel with dialogue space.",
            },
        ],
    }


def _mock_story_bible() -> dict:
    return {
        "logline": "A stubborn young artist unlocks living manga panels and must master them before a rival edits reality.",
        "synopsis": (
            "In the vertical city of Kurobay, apprentice artist Nami Vale discovers that her sketchbook can open "
            "panel-shaped portals into unfinished moments. Each panel changes the city when completed. When the "
            "masked editor Halcyon starts erasing neighborhoods to build a perfect final draft, Nami gathers allies "
            "and learns that messy human choices are the source of the city's magic."
        ),
        "genre": "Urban fantasy adventure",
        "themes": ["creative courage", "found family", "imperfection as power"],
        "target_audience": "Teen and young adult manga readers",
        "tone": "Energetic, heartfelt, mysterious",
        "main_conflict": "Nami must protect Kurobay from Halcyon, who can revise reality by stealing completed panels.",
        "world_rules": [
            "Living panels can alter only moments that are emotionally unresolved.",
            "A panel closes when the character inside makes an irreversible choice.",
            "Edits made without consent leave visible ink scars in the city."
        ],
        "characters": [
            {
                "name": "Nami Vale",
                "role": "Protagonist",
                "description": "An impulsive apprentice artist who treats every blank page like a dare.",
                "traits": ["inventive", "stubborn", "empathetic"],
                "visual_notes": "Short jacket, ink-stained fingers, bright panel-shaped hair clips."
            },
            {
                "name": "Jun Pike",
                "role": "Tactician",
                "description": "A calm delivery rider who knows every rooftop route and every rumor.",
                "traits": ["observant", "dry humor", "loyal"],
                "visual_notes": "Messenger bag, angular glasses, wind-swept scarf."
            },
            {
                "name": "Halcyon",
                "role": "Antagonist",
                "description": "A masked editor convinced the city must be rewritten into a flawless story.",
                "traits": ["precise", "charismatic", "ruthless"],
                "visual_notes": "White editor mask, black gloves, long coat lined with red correction marks."
            }
        ],
        "locations": [
            {
                "name": "Kurobay Rooftops",
                "description": "A layered skyline of water towers, antenna bridges, and hand-painted billboards.",
                "visual_notes": "Deep shadows, high contrast signs, dramatic perspective drops.",
                "rules": ["Rooftop shortcuts shift after each living panel closes."]
            },
            {
                "name": "The Ink Market",
                "description": "A night bazaar where artists barter brushes, rumors, and forbidden draft pages.",
                "visual_notes": "Lanterns, dense stalls, wet pavement reflections.",
                "rules": ["No one can erase a bargain written in black ink."]
            }
        ],
        "key_objects": [
            {
                "name": "The Margin Sketchbook",
                "description": "A battered sketchbook whose margins draw doors into living panels.",
                "significance": "It lets Nami enter unresolved story moments and choose how to complete them.",
                "visual_notes": "Frayed cover, silver corner protectors, pages that glow at panel borders."
            }
        ],
        "chapter_outline": [
            {
                "chapter_number": 1,
                "title": "The Door in the Margin",
                "summary": "Nami opens her first living panel and saves a block from being erased."
            },
            {
                "chapter_number": 2,
                "title": "Ink Market Rules",
                "summary": "Nami and Jun search for the sketchbook's origin while Halcyon hunts the next panel."
            },
            {
                "chapter_number": 3,
                "title": "Final Draft",
                "summary": "The crew confronts Halcyon inside a collapsing city-sized storyboard."
            }
        ],
        "continuity_rules": [
            "Nami cannot control a panel by force; she can only influence choices.",
            "Halcyon's red marks always foreshadow a coming rewrite.",
            "The sketchbook becomes heavier each time Nami avoids a hard truth."
        ],
        "style_bible": {
            "visual_style": "Crisp black inks with expressive faces, kinetic gutters, and detailed urban fantasy backgrounds.",
            "line_art": "Bold foreground silhouettes with finer architectural hatching in backgrounds.",
            "palette": "Black and white manga base with occasional teal story-energy accents in color editions.",
            "paneling": "Dynamic diagonals for action, quiet symmetrical frames for emotional decisions.",
            "lettering": "Clean hand-lettered dialogue, rough-edged narration boxes for sketchbook thoughts.",
            "negative_prompts": ["muddy anatomy", "blank backgrounds", "unreadable text"]
        }
    }


def _mock_chapter_plan() -> dict:
    return {
        "chapters": [
            {
                "chapter_number": 1,
                "title": "The Door in the Margin",
                "summary": "Nami discovers the Margin Sketchbook, enters a living panel, and stops Halcyon's first erasure.",
                "goal": "Introduce the story engine, Nami's flaw, and the cost of changing unfinished moments.",
                "scenes": [
                    {
                        "scene_order": 1,
                        "title": "Late Delivery",
                        "summary": "Nami races across the rooftops to deliver art samples before sunset.",
                        "location_name": "Kurobay Rooftops",
                        "emotional_turn": "Excitement turns into dread when the skyline begins to smear.",
                        "characters": ["Nami Vale", "Jun Pike"]
                    },
                    {
                        "scene_order": 2,
                        "title": "First Living Panel",
                        "summary": "The sketchbook opens a panel around a vanishing street musician.",
                        "location_name": "The Ink Market",
                        "emotional_turn": "Panic becomes resolve as Nami realizes the musician needs a choice, not rescue.",
                        "characters": ["Nami Vale", "Halcyon"]
                    }
                ]
            },
            {
                "chapter_number": 2,
                "title": "Ink Market Rules",
                "summary": "Jun guides Nami through the Ink Market to learn why the sketchbook chose her.",
                "goal": "Expand the world rules and reveal Halcyon's method.",
                "scenes": [
                    {
                        "scene_order": 1,
                        "title": "Bargain in Black Ink",
                        "summary": "A brushmaker trades information for Nami's promise to finish one abandoned panel.",
                        "location_name": "The Ink Market",
                        "emotional_turn": "Suspicion becomes commitment.",
                        "characters": ["Nami Vale", "Jun Pike"]
                    }
                ]
            }
        ]
    }


def _mock_page_plans() -> dict:
    return {
        "pages": [
            {
                "page_number": 1,
                "summary": "Nami sprints across the rooftops as the first signs of reality editing appear.",
                "pacing": "Fast open, then a sharp silent beat.",
                "panels": [
                    {
                        "panel_order": 1,
                        "story_beat": "Establish Kurobay's stacked skyline and Nami's speed.",
                        "shot_type": "wide shot",
                        "camera_angle": "high angle",
                        "characters": ["Nami Vale"],
                        "location": "Kurobay Rooftops",
                        "dialogue": None,
                        "narration": "Kurobay always looked unfinished from above.",
                        "visual_notes": "Strong perspective lines, rooftops layered like comic panels.",
                        "emotional_intent": "Wonder and momentum"
                    },
                    {
                        "panel_order": 2,
                        "story_beat": "Nami notices a billboard melting into red correction marks.",
                        "shot_type": "medium shot",
                        "camera_angle": "low angle",
                        "characters": ["Nami Vale"],
                        "location": "Kurobay Rooftops",
                        "dialogue": "That was not in the morning sketch.",
                        "narration": None,
                        "visual_notes": "Billboard letters smear like wet ink behind her.",
                        "emotional_intent": "Unease"
                    }
                ]
            },
            {
                "page_number": 2,
                "summary": "The Margin Sketchbook opens its first living panel around a disappearing musician.",
                "pacing": "Mystery beat into decisive action.",
                "panels": [
                    {
                        "panel_order": 1,
                        "story_beat": "Nami lands in the Ink Market and hears a song cutting in and out.",
                        "shot_type": "establishing shot",
                        "camera_angle": "street-level",
                        "characters": ["Nami Vale"],
                        "location": "The Ink Market",
                        "dialogue": None,
                        "narration": None,
                        "visual_notes": "Crowded stalls frame an empty circle around the musician.",
                        "emotional_intent": "Curiosity"
                    },
                    {
                        "panel_order": 2,
                        "story_beat": "The sketchbook draws a panel border around the musician's choice.",
                        "shot_type": "close-up",
                        "camera_angle": "over shoulder",
                        "characters": ["Nami Vale"],
                        "location": "The Ink Market",
                        "dialogue": "Okay, page. Show me what you want.",
                        "narration": None,
                        "visual_notes": "Glowing border reflected in Nami's eyes.",
                        "emotional_intent": "Resolve"
                    }
                ]
            }
        ]
    }
