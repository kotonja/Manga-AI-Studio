import { expect, test, type Page, type Route } from "@playwright/test";

const now = "2026-06-26T12:00:00.000Z";
const projectId = "project-alpha";
const pageId = "page-1";
const panelId = "panel-1";
const chapterId = "chapter-1";
const jobId = "job-founder";

const panels = [
  panel("panel-1", 96, 120, 1408, 780, 1),
  panel("panel-2", 96, 940, 668, 1280, 2),
  panel("panel-3", 836, 940, 668, 1280, 3)
];

const project = {
  id: projectId,
  name: "Ash Lantern Founder Demo",
  description: "A lonely swordsman protects a ghost child in a ruined city.",
  style_prompt: "Ruined Ink Elegy",
  status: "draft",
  active_style_bible_id: "style-1",
  allow_training: false,
  allow_product_improvement: false,
  data_collection_notes: "",
  created_at: now,
  updated_at: now
};

const projectDetail = {
  ...project,
  pages: [
    {
      id: pageId,
      project_id: projectId,
      page_number: 1,
      width: 1600,
      height: 2400,
      layout_json: {},
      created_at: now,
      updated_at: now,
      panels
    }
  ]
};

const storyBible = {
  id: "story-1",
  project_id: projectId,
  logline: "A scarred swordsman shelters a ghost child while a ruined city learns to breathe again.",
  synopsis: "Ren crosses a rain-black city carrying Mio's lantern. Each page reveals another piece of the city's grief and the vow binding them together.",
  genre: "dark fantasy",
  themes: ["grief", "guardianship", "hope"],
  target_audience: "teen",
  tone: "melancholic but brave",
  main_conflict: "Ren must protect Mio from ash spirits drawn to her light.",
  world_rules: ["Ghosts anchor to remembered objects."],
  characters: [
    { id: "char-ren", name: "Ren", role: "swordsman", description: "Quiet guardian", traits: ["lonely"], visual_notes: "long coat and chipped sword" },
    { id: "char-mio", name: "Mio", role: "ghost child", description: "Soft light in the ruins", traits: ["curious"], visual_notes: "lantern glow" }
  ],
  locations: [{ id: "loc-ruins", name: "Ruined City", description: "Broken towers under rain", visual_notes: "collapsed bridges", rules: [] }],
  key_objects: [{ id: "obj-lantern", name: "Lantern", description: "Mio's anchor", significance: "keeps her visible", visual_notes: "paper lantern" }],
  chapter_outline: [{ chapter_number: 1, title: "Ash Lantern", summary: "Ren and Mio cross the city." }],
  continuity_rules: ["Mio always appears near lantern light."],
  style_bible: null,
  created_at: now,
  updated_at: now
};

const chapters = [
  {
    id: chapterId,
    project_id: projectId,
    story_bible_id: "story-1",
    chapter_number: 1,
    title: "Ash Lantern",
    summary: "Ren escorts Mio through the ruined ward.",
    goal: "Reach the bell tower before dawn.",
    scenes: []
  }
];

const pagePlans = [
  {
    id: "plan-page-1",
    project_id: projectId,
    chapter_id: chapterId,
    page_number: 1,
    summary: "Ren discovers Mio beside a ruined fountain.",
    pacing: "quiet reveal",
    page_role: "reveal_page",
    emotional_intensity: 7,
    action_intensity: 3,
    dialogue_density: 2,
    silence_level: 8,
    reveal_level: 9,
    page_turn_importance: 8,
    recommended_page_type: "reveal_page",
    pacing_notes: "Hold silence before dialogue.",
    panels: [
      panelPlan(1, "Rain over the ruined city", "wide", "high"),
      panelPlan(2, "Ren notices the lantern", "medium", "low"),
      panelPlan(3, "Mio looks up", "close", "eye-level")
    ]
  }
];

const characters = [
  character("char-ren", "Ren", "Guardian swordsman", ["long coat", "chipped sword", "tired eyes"]),
  character("char-mio", "Mio", "Ghost child", ["small silhouette", "lantern halo", "transparent hair"])
];

const qaReport = {
  id: "qa-1",
  target_type: "page",
  target_id: pageId,
  issue_code: null,
  issue_category: null,
  severity: null,
  confidence: 1,
  page_id: pageId,
  panel_id: null,
  auto_fix_available: false,
  auto_fix_action: {},
  overall_score: 94,
  scores: { layout: 96, lettering: 92, export: 94 },
  issues: [],
  recommendations: [],
  blocking: false,
  created_at: now,
  updated_at: now
};

const exportPreset = {
  id: "archive_package",
  name: "Archive Package",
  description: "Final pages, metadata, provenance, and layered JSON.",
  page_width: 1600,
  page_height: 2400,
  dpi: 300,
  bleed: 32,
  safe_margin: 96,
  color_mode: "grayscale",
  reading_direction: "rtl",
  file_format: "zip",
  compression_quality: 92,
  required_qa_gates: ["no_blocking_qa"],
  options: {}
};

test.beforeEach(async ({ page }) => {
  await page.route("http://localhost:8000/**", mockApiRoute);
  await page.route("http://127.0.0.1:8000/**", mockApiRoute);
});

test.setTimeout(60_000);

test("dashboard loads and offers the founder demo", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Manga AI Studio" })).toBeVisible();
  await expect(page.getByRole("link", { name: /Founder Demo/ })).toBeVisible();
  await expect(page.getByText("Ash Lantern Founder Demo")).toBeVisible();
});

test("founder demo runs with one click and opens the studio project", async ({ page }) => {
  await page.goto("/demo");
  await expect(page.getByRole("heading", { name: "Generate a draft manga in one run" })).toBeVisible();
  await page.getByRole("button", { name: "Generate Manga Demo" }).click();
  await expect(page.getByText("94/100 average page score")).toBeVisible();
  await expect(page.getByRole("link", { name: /ZIP Package/ })).toBeVisible();
  await page.getByRole("link", { name: /Open in Studio/ }).click();
  await expect(page).toHaveURL(new RegExp(`/projects/${projectId}$`));
  await expect(page.locator("h1", { hasText: project.name })).toBeVisible();
});

test("core project rooms load", async ({ page }) => {
  await page.goto(`/projects/${projectId}`);
  await expect(page.locator("h1", { hasText: project.name })).toBeVisible();
  await expect(page.getByRole("link", { name: /Story Room/ }).first()).toBeVisible();
  await expect(page.getByRole("link", { name: /Page Studio/ }).first()).toBeVisible();

  await page.goto(`/projects/${projectId}/story`);
  await expect(page.getByRole("heading", { name: "Story Room" })).toBeVisible();
  await expect(page.getByText(storyBible.logline).first()).toBeVisible();

  await page.goto(`/projects/${projectId}/pages/${pageId}/studio`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Page Studio" })).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Provider" })).toBeVisible();

  await page.goto(`/projects/${projectId}/publishing`, { waitUntil: "domcontentloaded" });
  await expect(page.getByRole("heading", { name: "Publishing Room" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Archive Package/ })).toBeVisible();
});

async function mockApiRoute(route: Route) {
  const request = route.request();
  const url = new URL(request.url());
  const path = url.pathname;
  const method = request.method();

  if (path.startsWith("/assets/")) {
    return route.fulfill({
      status: 200,
      contentType: "image/png",
      body: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=",
        "base64"
      )
    });
  }

  if (method === "GET" && path === "/projects") return json(route, [project]);
  if (method === "POST" && path === "/demo/founder-run") return json(route, { job_id: jobId, project_id: projectId });
  if (method === "GET" && path === `/jobs/${jobId}`) return json(route, generationJob());
  if (method === "GET" && path === `/jobs/${jobId}/events`) return json(route, jobEvents());
  if (method === "GET" && path === `/projects/${projectId}`) return json(route, projectDetail);
  if (method === "GET" && path === `/projects/${projectId}/workspace-summary`) return json(route, workspaceSummary());
  if (method === "GET" && path === `/projects/${projectId}/versions`) return json(route, []);
  if (method === "GET" && path === `/projects/${projectId}/story/bible`) return json(route, storyBible);
  if (method === "GET" && path === `/projects/${projectId}/story/chapters`) return json(route, chapters);
  if (method === "GET" && path === `/chapters/${chapterId}/story/page-plans`) return json(route, pagePlans);
  if (method === "GET" && path === `/projects/${projectId}/characters`) return json(route, characters);
  if (method === "GET" && path === `/pages/${pageId}/composite`) return json(route, compositePage());
  if (method === "GET" && path === `/pages/${pageId}/qa/latest`) return json(route, qaReport);
  if (method === "GET" && path === `/pages/${pageId}/layout`) return json(route, pageLayout());
  if (method === "GET" && path === "/providers") return json(route, providerRegistry());
  if (method === "GET" && path === "/providers/mock/health") return json(route, providerHealth());
  if (method === "GET" && path === `/projects/${projectId}/layout-templates`) return json(route, []);
  if (method === "GET" && path === `/pages/${pageId}/reference-packs`) return json(route, { page_id: pageId, panels: [] });
  if (method === "GET" && path === "/export-presets") return json(route, [exportPreset]);
  if (method === "GET" && path === `/projects/${projectId}/publishing-metadata`) return json(route, publishingMetadata());
  if (method === "GET" && path === `/projects/${projectId}/export-readiness`) return json(route, exportReadiness());
  if (method === "GET" && path === "/learning/feedback-options") return json(route, feedbackOptions());
  if (method === "GET" && path.match(/^\/panels\/[^/]+\/(render-prompts|renders)$/)) return json(route, []);

  return json(route, {});
}

function json(route: Route, body: unknown) {
  return route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body)
  });
}

function panel(id: string, x: number, y: number, width: number, height: number, reading_order: number) {
  return {
    id,
    page_id: pageId,
    x,
    y,
    width,
    height,
    polygon: [
      { x, y },
      { x: x + width, y },
      { x: x + width, y: y + height },
      { x, y: y + height }
    ],
    reading_order,
    prompt: "black-and-white manga panel with Ren, Mio, rain, and ruins",
    created_at: now,
    updated_at: now
  };
}

function panelPlan(panel_order: number, story_beat: string, shot_type: string, camera_angle: string) {
  return {
    id: `panel-plan-${panel_order}`,
    page_plan_id: "plan-page-1",
    panel_order,
    story_beat,
    shot_type,
    camera_angle,
    characters: ["Ren", "Mio"],
    location: "Ruined City",
    dialogue: panel_order === 3 ? "You can see me?" : null,
    narration: null,
    visual_notes: "rain, cracked stone, careful negative space",
    emotional_intent: "lonely tenderness",
    beat_importance: 8,
    time_duration: "held beat",
    camera_motion: "still",
    motion_intensity: 2,
    dialogue_weight: 1,
    silence: panel_order !== 3,
    impact_level: panel_order === 1 ? 9 : 5,
    recommended_panel_size: panel_order === 1 ? "large" : "medium",
    transition_type: "moment-to-moment"
  };
}

function character(id: string, name: string, role: string, silhouette_keywords: string[]) {
  return {
    id,
    project_id: projectId,
    name,
    aliases: [],
    age_range: "",
    role,
    personality: `${name} is quiet, alert, and protective.`,
    face_description: "clear facial anchor",
    hair_description: "recognizable hair anchor",
    eye_description: "expressive eyes",
    body_type: "slender",
    outfit_default: "travel cloak",
    accessories: [],
    scars_marks: "",
    voice_style: "spare",
    forbidden_changes: [],
    continuity_rules: [],
    canonical_visual_summary: `${name} has a distinctive silhouette and readable manga identity.`,
    silhouette_keywords,
    face_anchor_description: "consistent face shape",
    hair_anchor_description: "consistent hair shape",
    eye_anchor_description: "consistent eyes",
    body_anchor_description: "consistent body language",
    outfit_anchor_description: "consistent outfit",
    color_notes_even_for_bw: "high-contrast values",
    recurring_props: [],
    allowed_variations: [],
    forbidden_variations: [],
    current_story_state: "crossing the ruined city",
    injury_state: "uninjured",
    emotional_baseline: "guarded",
    reference_asset_ids: [],
    approved_panel_asset_ids: [],
    created_at: now,
    updated_at: now
  };
}

function generationJob() {
  return {
    id: jobId,
    project_id: projectId,
    page_id: null,
    panel_id: null,
    provider: "mock",
    job_type: "director_generate_draft",
    status: "succeeded",
    input_payload: {},
    output_payload: { founder_state: { exports: { zip: "export-zip", pdf: "export-pdf" } } },
    error_message: null,
    created_at: now,
    updated_at: now,
    render: null
  };
}

function jobEvents() {
  return [
    event("creating_project", "Creating project"),
    event("writing_story_bible", "Writing story bible"),
    event("designing_characters", "Designing characters"),
    event("composing_final_pages", "Composing pages"),
    event("checking_quality", "Checking quality"),
    event("exporting_files", "Exporting files"),
    event("complete", "Demo complete")
  ];
}

function event(event_type: string, message: string) {
  return {
    id: `event-${event_type}`,
    job_id: jobId,
    event_type,
    message,
    payload: {},
    created_at: now,
    updated_at: now
  };
}

function workspaceSummary() {
  return {
    project_id: projectId,
    active_chapter_title: "Ash Lantern",
    page_count: 1,
    panel_count: 3,
    rendered_panel_count: 3,
    render_progress: 1,
    qa_score: 94,
    qa_blocking: false,
    export_status: "succeeded",
    active_job_count: 0,
    status_chip: "QA Passed"
  };
}

function compositePage() {
  return {
    id: "composite-1",
    page_id: pageId,
    project_id: projectId,
    filename: "page-001.png",
    storage_key: "composites/page-001.png",
    public_url: null,
    content_type: "image/png",
    size_bytes: 2048,
    width: 1600,
    height: 2400,
    reading_direction: "rtl",
    metadata_json: {},
    created_at: now,
    updated_at: now
  };
}

function pageLayout() {
  return {
    page_id: pageId,
    width: 1600,
    height: 2400,
    bleed: 32,
    safe_margin: 96,
    reading_direction: "rtl",
    qa_overlay_enabled: true,
    panels: panels.map((item) => ({ ...item, bubbles: [] }))
  };
}

function providerRegistry() {
  return [
    {
      name: "mock",
      display_name: "Mock Image Provider",
      model_name: "mock-manga-v1",
      capabilities: {
        supports_image_generation: true,
        supports_image_editing: false,
        supports_references: true,
        supports_seeds: true,
        supports_async_jobs: false
      },
      max_resolution: { width: 2048, height: 2048 },
      requires_env_vars: [],
      configured: true,
      missing_env_vars: [],
      cost_warning: "No cost. Deterministic local placeholder.",
      notes: "Used for tests and private alpha demos."
    }
  ];
}

function providerHealth() {
  return {
    name: "mock",
    status: "healthy",
    configured: true,
    message: "Mock provider ready",
    checked_at: now,
    details: {}
  };
}

function publishingMetadata() {
  return {
    id: "metadata-1",
    project_id: projectId,
    title: project.name,
    subtitle: "",
    author_name: "Alpha Tester",
    publisher: "",
    language: "en",
    synopsis: project.description,
    age_rating: "Teen",
    genres: ["dark fantasy"],
    tags: ["demo"],
    copyright_notice: "",
    ai_disclosure_text: "Mock AI-assisted draft generated locally.",
    metadata_json: {},
    created_at: now,
    updated_at: now
  };
}

function exportReadiness() {
  return {
    project_id: projectId,
    preset: exportPreset,
    ready: true,
    force_required: false,
    checklist: [
      { key: "pages_composed", label: "All pages composed", passed: true, severity: "info", message: "Ready", details: {} },
      { key: "no_blocking_qa", label: "No blocking QA issues", passed: true, severity: "info", message: "Ready", details: {} }
    ],
    page_count: 1,
    blocking_issue_count: 0,
    metadata: publishingMetadata()
  };
}

function feedbackOptions() {
  return {
    issue_tags: [
      { id: "wrong character", label: "Wrong Character" },
      { id: "confusing layout", label: "Confusing Layout" }
    ],
    default_allow_use_for_product_improvement: false,
    collection_explanation: "Private by default."
  };
}
