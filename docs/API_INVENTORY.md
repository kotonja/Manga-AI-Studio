# API Inventory

Generated at: 2026-06-26T13:42:55.792564+00:00

| Method | Path | Request Body | Response Shape | Auth | Status | Test Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| GET | `/admin/ai-task-runs` | `none` | `list[AITaskRunRead]` | admin/dev flag | PARTIAL | yes |
| GET | `/admin/alpha-dashboard` | `none` | `AlphaDashboardRead` | admin/dev flag | PARTIAL | no |
| GET | `/admin/improvement-report` | `none` | `ImprovementReportRead` | admin/dev flag | PARTIAL | yes |
| GET | `/admin/prompt-templates` | `none` | `list[PromptTemplateRead]` | admin/dev flag | PARTIAL | no |
| GET | `/alpha/onboarding` | `none` | `AlphaOnboardingInfo` | public | WORKING | yes |
| GET | `/assets/{asset_id}/download` | `none` | `not declared` | alpha user/project owner | WORKING | yes |
| GET | `/assets/{asset_id}/provenance` | `none` | `AssetProvenanceRead` | alpha user/project owner | WORKING | yes |
| PUT | `/assets/{asset_id}/provenance` | `AssetProvenanceUpdate` | `AssetProvenanceRead` | alpha user/project owner | WORKING | yes |
| PUT | `/bubbles/{bubble_id}` | `BubbleUpdate` | `BubbleRead` | alpha user/project owner | WORKING | yes |
| POST | `/chapters/{chapter_id}/pacing/rebalance` | `none` | `PacingRebalanceResult` | alpha user/project owner | WORKING | yes |
| POST | `/chapters/{chapter_id}/story/generate-page-plans` | `none` | `list[PagePlanResult]` | alpha user/project owner | WORKING | yes |
| GET | `/chapters/{chapter_id}/story/page-plans` | `none` | `list[PagePlanResult]` | alpha user/project owner | WORKING | yes |
| PUT | `/character-states/{state_id}` | `CharacterStateUpdate` | `CharacterStateRead` | alpha user/project owner | WORKING | yes |
| DELETE | `/characters/{character_id}` | `none` | `not declared` | alpha user/project owner | WORKING | yes |
| GET | `/characters/{character_id}` | `none` | `CharacterCardRead` | alpha user/project owner | WORKING | yes |
| PUT | `/characters/{character_id}` | `CharacterCardUpdate` | `CharacterCardRead` | alpha user/project owner | WORKING | yes |
| POST | `/characters/{character_id}/generate-character-sheet` | `none` | `GenerateCharacterSheetResult` | alpha user/project owner | WORKING | yes |
| GET | `/characters/{character_id}/reference-assets` | `none` | `list[CharacterReferenceAssetRead]` | alpha user/project owner | WORKING | yes |
| POST | `/characters/{character_id}/reference-assets` | `ReferenceAssetCreate` | `CharacterReferenceAssetRead` | alpha user/project owner | WORKING | yes |
| GET | `/characters/{character_id}/states` | `none` | `list[CharacterStateRead]` | alpha user/project owner | WORKING | yes |
| POST | `/characters/{character_id}/states` | `CharacterStateCreate` | `CharacterStateRead` | alpha user/project owner | WORKING | yes |
| POST | `/commands/execute` | `CommandExecuteRequest` | `CommandExecuteResult` | alpha user/project owner | WORKING | yes |
| POST | `/commands/interpret` | `CommandInterpretRequest` | `CommandInterpretResult` | alpha user/project owner | WORKING | yes |
| POST | `/demo/create-full-project` | `none` | `DemoPipelineResult` | alpha user | WORKING | yes |
| POST | `/demo/founder-run` | `FounderDemoRunRequest` | `FounderDemoRunResponse` | alpha user | WORKING | yes |
| POST | `/eval/run` | `EvalRunRequest` | `EvalRunReport` | admin/dev flag | WORKING | yes |
| GET | `/eval/scenarios` | `none` | `list[EvalScenarioRead]` | admin/dev flag | PARTIAL | no |
| GET | `/export-presets` | `none` | `list[ExportPresetRead]` | alpha user/project owner | PARTIAL | no |
| GET | `/exports/{export_id}` | `none` | `ExportRead` | alpha user/project owner | WORKING | yes |
| GET | `/exports/{export_id}/download` | `none` | `not declared` | alpha user/project owner | WORKING | yes |
| POST | `/feedback` | `FeedbackCreate` | `FeedbackRead` | public or project owner | WORKING | yes |
| GET | `/health` | `none` | `Response Health Health Get` | public | WORKING | yes |
| GET | `/health/db` | `none` | `not declared` | public | WORKING | no |
| GET | `/health/redis` | `none` | `not declared` | public | WORKING | no |
| GET | `/health/storage` | `none` | `not declared` | public | WORKING | no |
| GET | `/health/worker` | `none` | `not declared` | public | WORKING | no |
| POST | `/jobs/mock-render-panel` | `MockRenderPanelRequest` | `GenerationJobRead` | alpha user/project owner | WORKING | yes |
| POST | `/jobs/render-panel` | `RenderPanelRequest` | `GenerationJobRead` | alpha user/project owner | WORKING | yes |
| GET | `/jobs/{job_id}` | `none` | `GenerationJobDetail` | alpha user/project owner | WORKING | yes |
| GET | `/jobs/{job_id}/events` | `none` | `list[JobEventRead]` | alpha user/project owner | WORKING | yes |
| POST | `/jobs/{job_id}/retry` | `JobRetryRequest | null` | `GenerationJobRetryResult` | alpha user/project owner | WORKING | yes |
| POST | `/learning/feedback` | `GenerationFeedbackCreate` | `GenerationFeedbackRead` | alpha user/project owner | WORKING | yes |
| GET | `/learning/feedback-options` | `none` | `LearningFeedbackOptions` | public | PARTIAL | no |
| POST | `/pages/{page_id}/compose` | `none` | `CompositePageRead` | alpha user/project owner | WORKING | yes |
| GET | `/pages/{page_id}/composite` | `none` | `CompositePageRead` | alpha user/project owner | WORKING | yes |
| GET | `/pages/{page_id}/layout` | `none` | `PageLayoutRead` | alpha user/project owner | WORKING | yes |
| PUT | `/pages/{page_id}/layout` | `PageLayoutUpdate` | `PageLayoutRead` | alpha user/project owner | WORKING | yes |
| POST | `/pages/{page_id}/layout/suggest` | `LayoutSuggestRequest` | `LayoutSuggestionRead` | alpha user/project owner | WORKING | yes |
| GET | `/pages/{page_id}/lettering` | `none` | `LetteringPageRead` | alpha user/project owner | WORKING | yes |
| GET | `/pages/{page_id}/lettering.svg` | `none` | `not declared` | alpha user/project owner | WORKING | yes |
| POST | `/pages/{page_id}/lettering/generate` | `none` | `LetteringGenerateResult` | alpha user/project owner | WORKING | yes |
| POST | `/pages/{page_id}/panels` | `PanelCreate` | `PanelRead` | alpha user/project owner | WORKING | yes |
| POST | `/pages/{page_id}/qa` | `QARequest | null` | `QAReportRead` | alpha user/project owner | WORKING | yes |
| POST | `/pages/{page_id}/qa/auto-fix-safe` | `none` | `QAAutoFixResult` | alpha user/project owner | WORKING | yes |
| GET | `/pages/{page_id}/qa/latest` | `none` | `QAReportRead` | alpha user/project owner | WORKING | yes |
| GET | `/pages/{page_id}/reference-packs` | `none` | `PageReferencePacksRead` | alpha user/project owner | WORKING | yes |
| POST | `/pages/{page_id}/sfx` | `SFXElementCreate` | `SFXElementRead` | alpha user/project owner | WORKING | yes |
| POST | `/panels/{panel_id}/bubbles` | `BubbleCreate` | `BubbleRead` | alpha user/project owner | WORKING | yes |
| GET | `/panels/{panel_id}/reference-pack` | `none` | `ReferencePackRead` | alpha user/project owner | WORKING | yes |
| POST | `/panels/{panel_id}/render` | `PanelRenderRequest` | `PanelRenderStartResult` | alpha user/project owner | WORKING | yes |
| POST | `/panels/{panel_id}/render-dry-run` | `PanelRenderRequest` | `PanelRenderDryRunResult` | alpha user/project owner | WORKING | yes |
| GET | `/panels/{panel_id}/render-prompts` | `none` | `list[PanelRenderPromptRead]` | alpha user/project owner | WORKING | yes |
| GET | `/panels/{panel_id}/renders` | `none` | `list[PanelRenderHistoryItem]` | alpha user/project owner | WORKING | yes |
| POST | `/panels/{panel_id}/rerender` | `PanelRerenderRequest` | `PanelRenderStartResult` | alpha user/project owner | WORKING | yes |
| GET | `/projects` | `none` | `list[ProjectRead]` | alpha user/project owner | WORKING | yes |
| POST | `/projects` | `ProjectCreate` | `ProjectRead` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}` | `none` | `ProjectDetail` | alpha user/project owner | WORKING | yes |
| PUT | `/projects/{project_id}/active-style` | `ActiveStyleUpdate` | `StyleBibleLabRead` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/characters` | `none` | `list[CharacterCardRead]` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/characters` | `CharacterCardCreate` | `CharacterCardRead` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/checkpoint` | `CheckpointCreate` | `list[VersionRead]` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/commands` | `none` | `list[CommandHistoryRead]` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/data-controls` | `none` | `ProjectDataControlsRead` | alpha user/project owner | WORKING | yes |
| PUT | `/projects/{project_id}/data-controls` | `ProjectDataControlsUpdate` | `ProjectDataControlsRead` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/director/generate-draft` | `DirectorGenerateDraftRequest` | `DirectorGenerateDraftResponse` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/export-readiness` | `none` | `ExportReadinessResult` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/exports` | `ExportCreate` | `ExportRead` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/exports/create` | `ExportCreateAdvanced` | `ExportRead` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/exports/preview` | `ExportCreateAdvanced | null` | `ExportPreviewResult` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/layout-templates` | `none` | `list[LayoutTemplateRead]` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/layout-templates` | `LayoutTemplateCreate` | `LayoutTemplateRead` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/pacing/analyze` | `none` | `PacingAnalysisResult` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/pages` | `PageCreate` | `PageRead` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/provenance` | `none` | `ProjectProvenanceRead` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/publishing-metadata` | `none` | `ProjectPublishingMetadataRead` | alpha user/project owner | WORKING | yes |
| PUT | `/projects/{project_id}/publishing-metadata` | `ProjectPublishingMetadataUpsert` | `ProjectPublishingMetadataRead` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/qa/run-full` | `QARequest | null` | `QAProjectRunResult` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/rights-declaration` | `none` | `RightsDeclarationRead | null` | alpha user/project owner | WORKING | yes |
| PUT | `/projects/{project_id}/rights-declaration` | `RightsDeclarationUpsert` | `RightsDeclarationRead` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/story/bible` | `none` | `StoryBibleResult` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/story/chapters` | `none` | `list[ChapterPlanResult]` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/story/generate-bible` | `StoryBibleCreate` | `StoryBibleResult` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/story/generate-chapter-plan` | `none` | `list[ChapterPlanResult]` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/style-bibles` | `none` | `list[StyleBibleLabRead]` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/style-bibles` | `StyleBibleLabCreate` | `StyleBibleLabRead` | alpha user/project owner | WORKING | yes |
| POST | `/projects/{project_id}/style/generate-dna` | `StyleDNAGenerateRequest` | `StyleDNAOptionsResult` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/versions` | `none` | `list[VersionRead]` | alpha user/project owner | WORKING | yes |
| GET | `/projects/{project_id}/workspace-summary` | `none` | `ProjectWorkspaceSummary` | alpha user/project owner | WORKING | yes |
| GET | `/providers` | `none` | `list[ProviderRead]` | sensitive alpha | WORKING | yes |
| GET | `/providers/{name}/health` | `none` | `ProviderHealthRead` | sensitive alpha | WORKING | yes |
| POST | `/qa/{report_id}/apply-fix` | `QAAutoFixRequest | null` | `QAAutoFixResult` | alpha user/project owner | PARTIAL | no |
| POST | `/renders/{render_id}/approve` | `none` | `PanelRenderHistoryItem` | alpha user/project owner | WORKING | yes |
| POST | `/safety/check` | `SafetyCheckRequest` | `SafetyCheckResult` | alpha user/project owner | WORKING | yes |
| DELETE | `/sfx/{sfx_id}` | `none` | `not declared` | alpha user/project owner | PARTIAL | no |
| PUT | `/sfx/{sfx_id}` | `SFXElementUpdate` | `SFXElementRead` | alpha user/project owner | PARTIAL | no |
| DELETE | `/style-bibles/{style_bible_id}` | `none` | `not declared` | alpha user/project owner | WORKING | yes |
| GET | `/style-bibles/{style_bible_id}` | `none` | `StyleBibleLabRead` | alpha user/project owner | WORKING | yes |
| PUT | `/style-bibles/{style_bible_id}` | `StyleBibleLabUpdate` | `StyleBibleLabRead` | alpha user/project owner | WORKING | yes |
| POST | `/style-bibles/{style_bible_id}/mock-preview-panel` | `none` | `StylePreviewResult` | alpha user/project owner | WORKING | yes |
| POST | `/style-bibles/{style_bible_id}/sample-assets` | `StyleSampleAssetCreate` | `StyleSampleAssetRead` | alpha user/project owner | WORKING | yes |
| POST | `/style/guard` | `StyleBibleLabCreate` | `StyleGuardResult` | alpha user/project owner | PARTIAL | no |
| POST | `/style/ip-guard` | `SafetyCheckRequest` | `SafetyCheckResult` | alpha user/project owner | PARTIAL | no |
| GET | `/versions/{version_a}/diff/{version_b}` | `none` | `VersionDiffResult` | alpha user/project owner | WORKING | yes |
| POST | `/versions/{version_id}/restore` | `none` | `VersionRestoreResult` | alpha user/project owner | WORKING | yes |

Auth note: local development is unlocked by default. Private alpha can enable per-user token auth or signed browser sessions; project resources are owner-scoped when alpha auth is enabled. `ALPHA_SHARED_PASSWORD` is a shared single-account mode only. Browser sessions require `ALPHA_SESSION_SECRET`. External forwarded identity headers are trusted only when `TRUST_EXTERNAL_AUTH_HEADERS=true` behind a trusted proxy. Admin/dev routes require dev/admin flags or a signed admin session and must not be exposed publicly.
