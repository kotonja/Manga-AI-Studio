# API Inventory

Generated at: 2026-06-25T18:29:37.545311+00:00

| Method | Path | Request Body | Response Shape | Auth | Status | Test Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| GET | `/admin/ai-task-runs` | `none` | `list[AITaskRunRead]` | dev flag | PARTIAL | yes |
| GET | `/admin/prompt-templates` | `none` | `list[PromptTemplateRead]` | dev flag | PARTIAL | no |
| GET | `/assets/{asset_id}/provenance` | `none` | `AssetProvenanceRead` | none | WORKING | yes |
| PUT | `/assets/{asset_id}/provenance` | `AssetProvenanceUpdate` | `AssetProvenanceRead` | none | WORKING | yes |
| PUT | `/bubbles/{bubble_id}` | `BubbleUpdate` | `BubbleRead` | none | WORKING | yes |
| POST | `/chapters/{chapter_id}/story/generate-page-plans` | `none` | `list[PagePlanResult]` | none | WORKING | yes |
| PUT | `/character-states/{state_id}` | `CharacterStateUpdate` | `CharacterStateRead` | none | WORKING | yes |
| DELETE | `/characters/{character_id}` | `none` | `not declared` | none | WORKING | yes |
| GET | `/characters/{character_id}` | `none` | `CharacterCardRead` | none | WORKING | yes |
| PUT | `/characters/{character_id}` | `CharacterCardUpdate` | `CharacterCardRead` | none | WORKING | yes |
| POST | `/characters/{character_id}/generate-character-sheet` | `none` | `GenerateCharacterSheetResult` | none | WORKING | yes |
| GET | `/characters/{character_id}/reference-assets` | `none` | `list[CharacterReferenceAssetRead]` | none | WORKING | yes |
| POST | `/characters/{character_id}/reference-assets` | `ReferenceAssetCreate` | `CharacterReferenceAssetRead` | none | WORKING | yes |
| GET | `/characters/{character_id}/states` | `none` | `list[CharacterStateRead]` | none | WORKING | yes |
| POST | `/characters/{character_id}/states` | `CharacterStateCreate` | `CharacterStateRead` | none | WORKING | yes |
| POST | `/demo/create-full-project` | `none` | `DemoPipelineResult` | none | WORKING | yes |
| POST | `/eval/run` | `EvalRunRequest` | `EvalRunReport` | none | WORKING | yes |
| GET | `/eval/scenarios` | `none` | `list[EvalScenarioRead]` | none | PARTIAL | no |
| GET | `/exports/{export_id}` | `none` | `ExportRead` | none | WORKING | yes |
| GET | `/exports/{export_id}/download` | `none` | `not declared` | none | WORKING | yes |
| GET | `/health` | `none` | `Response Health Health Get` | none | WORKING | no |
| GET | `/health/db` | `none` | `not declared` | none | WORKING | no |
| GET | `/health/redis` | `none` | `not declared` | none | WORKING | no |
| GET | `/health/storage` | `none` | `not declared` | none | WORKING | no |
| GET | `/health/worker` | `none` | `not declared` | none | WORKING | no |
| POST | `/jobs/mock-render-panel` | `MockRenderPanelRequest` | `GenerationJobRead` | none | WORKING | yes |
| POST | `/jobs/render-panel` | `RenderPanelRequest` | `GenerationJobRead` | none | WORKING | yes |
| GET | `/jobs/{job_id}` | `none` | `GenerationJobDetail` | none | WORKING | yes |
| GET | `/jobs/{job_id}/events` | `none` | `list[JobEventRead]` | none | WORKING | yes |
| POST | `/pages/{page_id}/compose` | `none` | `CompositePageRead` | none | WORKING | yes |
| GET | `/pages/{page_id}/composite` | `none` | `CompositePageRead` | none | WORKING | yes |
| GET | `/pages/{page_id}/layout` | `none` | `PageLayoutRead` | none | WORKING | yes |
| PUT | `/pages/{page_id}/layout` | `PageLayoutUpdate` | `PageLayoutRead` | none | WORKING | yes |
| POST | `/pages/{page_id}/layout/suggest` | `LayoutSuggestRequest` | `LayoutSuggestionRead` | none | WORKING | yes |
| GET | `/pages/{page_id}/lettering` | `none` | `LetteringPageRead` | none | WORKING | yes |
| GET | `/pages/{page_id}/lettering.svg` | `none` | `not declared` | none | WORKING | yes |
| POST | `/pages/{page_id}/lettering/generate` | `none` | `LetteringGenerateResult` | none | WORKING | yes |
| POST | `/pages/{page_id}/panels` | `PanelCreate` | `PanelRead` | none | WORKING | yes |
| POST | `/pages/{page_id}/qa` | `QARequest | null` | `QAReportRead` | none | WORKING | yes |
| POST | `/pages/{page_id}/qa/auto-fix-safe` | `none` | `QAAutoFixResult` | none | WORKING | yes |
| GET | `/pages/{page_id}/qa/latest` | `none` | `QAReportRead` | none | WORKING | yes |
| GET | `/pages/{page_id}/reference-packs` | `none` | `PageReferencePacksRead` | none | WORKING | yes |
| POST | `/pages/{page_id}/sfx` | `SFXElementCreate` | `SFXElementRead` | none | WORKING | yes |
| POST | `/panels/{panel_id}/bubbles` | `BubbleCreate` | `BubbleRead` | none | WORKING | yes |
| GET | `/panels/{panel_id}/reference-pack` | `none` | `ReferencePackRead` | none | WORKING | yes |
| POST | `/panels/{panel_id}/render` | `PanelRenderRequest` | `PanelRenderStartResult` | none | WORKING | yes |
| GET | `/panels/{panel_id}/render-prompts` | `none` | `list[PanelRenderPromptRead]` | none | WORKING | yes |
| GET | `/panels/{panel_id}/renders` | `none` | `list[PanelRenderHistoryItem]` | none | WORKING | yes |
| POST | `/panels/{panel_id}/rerender` | `PanelRerenderRequest` | `PanelRenderStartResult` | none | WORKING | yes |
| GET | `/projects` | `none` | `list[ProjectRead]` | none | WORKING | yes |
| POST | `/projects` | `ProjectCreate` | `ProjectRead` | none | WORKING | yes |
| GET | `/projects/{project_id}` | `none` | `ProjectDetail` | none | WORKING | yes |
| PUT | `/projects/{project_id}/active-style` | `ActiveStyleUpdate` | `StyleBibleLabRead` | none | WORKING | yes |
| GET | `/projects/{project_id}/characters` | `none` | `list[CharacterCardRead]` | none | WORKING | yes |
| POST | `/projects/{project_id}/characters` | `CharacterCardCreate` | `CharacterCardRead` | none | WORKING | yes |
| POST | `/projects/{project_id}/checkpoint` | `CheckpointCreate` | `list[VersionRead]` | none | WORKING | yes |
| POST | `/projects/{project_id}/director/generate-draft` | `DirectorGenerateDraftRequest` | `DirectorGenerateDraftResponse` | none | WORKING | yes |
| POST | `/projects/{project_id}/exports` | `ExportCreate` | `ExportRead` | none | WORKING | yes |
| GET | `/projects/{project_id}/layout-templates` | `none` | `list[LayoutTemplateRead]` | none | WORKING | yes |
| POST | `/projects/{project_id}/layout-templates` | `LayoutTemplateCreate` | `LayoutTemplateRead` | none | WORKING | yes |
| POST | `/projects/{project_id}/pages` | `PageCreate` | `PageRead` | none | WORKING | yes |
| GET | `/projects/{project_id}/provenance` | `none` | `ProjectProvenanceRead` | none | WORKING | yes |
| POST | `/projects/{project_id}/qa/run-full` | `QARequest | null` | `QAProjectRunResult` | none | WORKING | yes |
| GET | `/projects/{project_id}/rights-declaration` | `none` | `RightsDeclarationRead | null` | none | WORKING | yes |
| PUT | `/projects/{project_id}/rights-declaration` | `RightsDeclarationUpsert` | `RightsDeclarationRead` | none | WORKING | yes |
| GET | `/projects/{project_id}/story/bible` | `none` | `StoryBibleResult` | none | WORKING | yes |
| POST | `/projects/{project_id}/story/generate-bible` | `StoryBibleCreate` | `StoryBibleResult` | none | WORKING | yes |
| POST | `/projects/{project_id}/story/generate-chapter-plan` | `none` | `list[ChapterPlanResult]` | none | WORKING | yes |
| GET | `/projects/{project_id}/style-bibles` | `none` | `list[StyleBibleLabRead]` | none | WORKING | yes |
| POST | `/projects/{project_id}/style-bibles` | `StyleBibleLabCreate` | `StyleBibleLabRead` | none | WORKING | yes |
| POST | `/projects/{project_id}/style/generate-dna` | `StyleDNAGenerateRequest` | `StyleDNAOptionsResult` | none | WORKING | yes |
| GET | `/projects/{project_id}/versions` | `none` | `list[VersionRead]` | none | WORKING | yes |
| GET | `/projects/{project_id}/workspace-summary` | `none` | `ProjectWorkspaceSummary` | none | WORKING | yes |
| POST | `/qa/{report_id}/apply-fix` | `QAAutoFixRequest | null` | `QAAutoFixResult` | none | PARTIAL | no |
| POST | `/renders/{render_id}/approve` | `none` | `PanelRenderHistoryItem` | none | WORKING | yes |
| POST | `/safety/check` | `SafetyCheckRequest` | `SafetyCheckResult` | none | WORKING | yes |
| DELETE | `/sfx/{sfx_id}` | `none` | `not declared` | none | PARTIAL | no |
| PUT | `/sfx/{sfx_id}` | `SFXElementUpdate` | `SFXElementRead` | none | PARTIAL | no |
| DELETE | `/style-bibles/{style_bible_id}` | `none` | `not declared` | none | WORKING | yes |
| GET | `/style-bibles/{style_bible_id}` | `none` | `StyleBibleLabRead` | none | WORKING | yes |
| PUT | `/style-bibles/{style_bible_id}` | `StyleBibleLabUpdate` | `StyleBibleLabRead` | none | WORKING | yes |
| POST | `/style-bibles/{style_bible_id}/mock-preview-panel` | `none` | `StylePreviewResult` | none | WORKING | yes |
| POST | `/style-bibles/{style_bible_id}/sample-assets` | `StyleSampleAssetCreate` | `StyleSampleAssetRead` | none | WORKING | yes |
| POST | `/style/guard` | `StyleBibleLabCreate` | `StyleGuardResult` | none | PARTIAL | no |
| POST | `/style/ip-guard` | `SafetyCheckRequest` | `SafetyCheckResult` | none | PARTIAL | no |
| GET | `/versions/{version_a}/diff/{version_b}` | `none` | `VersionDiffResult` | none | WORKING | yes |
| POST | `/versions/{version_id}/restore` | `none` | `VersionRestoreResult` | none | WORKING | yes |

Auth note: the MVP has no user authentication. Admin routes are protected only by the development flag and must not be exposed publicly.
