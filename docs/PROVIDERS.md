# Image Providers

Manga AI Studio supports provider-based panel rendering while keeping deterministic mock mode as the default safe path for tests and local demos.

## Providers

### Mock

- Name: `mock`
- Env vars: none
- Cost: none
- Use for: tests, demos, offline development, safe UI validation
- Behavior: creates deterministic local PNG placeholders with manga-style panel treatment

### OpenAI

- Name: `openai`
- Env vars:
  - `OPENAI_API_KEY`
  - `OPENAI_IMAGE_MODEL`
- Cost: real image generation may incur API charges
- Health behavior: verifies configuration only; it does not call paid generation APIs
- Current support: image generation
- Editing support: intentionally disabled until the edit flow is fully specified

Example:

```env
OPENAI_API_KEY=sk-your-key
OPENAI_IMAGE_MODEL=gpt-image-1.5
```

### ComfyUI

- Name: `comfyui`
- Env vars:
  - `COMFYUI_BASE_URL`
- Cost: depends on your local or remote ComfyUI deployment
- Health behavior: checks `/system_stats`
- Current support: submits workflow templates to the ComfyUI queue when configured
- Output retrieval: provider-specific and still intentionally guarded

Example:

```env
COMFYUI_BASE_URL=http://localhost:8188
```

## Provider Health

List providers:

```bash
curl http://localhost:8000/providers
```

Check one provider:

```bash
curl http://localhost:8000/providers/mock/health
curl http://localhost:8000/providers/openai/health
curl http://localhost:8000/providers/comfyui/health
```

Provider responses include:

- configured/not configured
- missing environment variables
- capabilities
- max resolution
- health status
- cost warning

## Dry-Run Before Rendering

Dry-run builds the full panel render prompt and validates provider configuration without calling paid APIs.

```bash
curl -X POST http://localhost:8000/panels/<panel-id>/render-dry-run \
  -H "Content-Type: application/json" \
  -d '{"provider_name":"openai","render_mode":"draft"}'
```

Dry-run returns:

- assembled prompt
- provider configured state
- requested size
- quality mode
- estimated cost if available
- warnings
- `can_render`

## Avoiding Accidental Paid Calls

- Keep `render_provider` set to `mock` unless you are deliberately testing a real provider.
- Use `/providers` and `/providers/{name}/health` before rendering.
- Use `/panels/{id}/render-dry-run` before real provider renders.
- The frontend warns when a selected provider may cost money.
- Tests set background jobs off and never require OpenAI or ComfyUI credentials.
- Missing provider env vars fail cleanly and store safe error metadata on the render job.

## Failure Handling

Provider failures are stored on the `GenerationJob`:

- `status=failed`
- clean `error_message`
- `output_payload.error_metadata`
- `output_payload.cost_metadata`
- `retry_provider=mock`

The worker marks failed render jobs cleanly and does not crash on expected provider failures.

## Cost Metadata

Render jobs store:

- provider
- model
- requested size
- quality mode
- estimated cost when available
- actual usage when providers return it
- started/completed timestamps
- duration

Mock renders always estimate `0.0 USD`.
