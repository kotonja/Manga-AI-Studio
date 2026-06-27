# Alpha Deployment Smoke Commands

These commands assume a single-host Docker Compose alpha deployment in mock mode.

Use PowerShell on Windows. On Linux/macOS, remove the `$env:` syntax and use shell exports or an `.env.alpha` file.

## Create Tester Tokens

Generate one token per tester:

```powershell
python scripts/create-alpha-token.py --user tester-a --write
python scripts/create-alpha-token.py --user tester-b --write
```

Copy the generated `user:token` pairs into `.env.alpha`:

```text
ALPHA_USER_TOKENS=tester-a:replace-with-token-a,tester-b:replace-with-token-b
```

Generate admin/session secrets with a password manager or secret manager. Do not commit them.

## Validate Env

Copy the template and replace every placeholder:

```powershell
Copy-Item .env.alpha.example .env.alpha
notepad .env.alpha
```

Validate:

```powershell
python scripts/check-alpha-env.py --env-file .env.alpha
```

The template intentionally fails until placeholders are replaced.

## Start Stack

Build and start with the alpha env file:

```powershell
docker compose --env-file .env.alpha up --build -d
```

Watch startup logs:

```powershell
docker compose --env-file .env.alpha logs -f api worker web
```

## Run Health Checks

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8000/health/db
curl.exe http://localhost:8000/health/redis
curl.exe http://localhost:8000/health/storage
curl.exe http://localhost:8000/health/worker
```

## Run Alpha Readiness

Set the admin token for your shell:

```powershell
$env:ALPHA_ADMIN_TOKEN = "replace-with-admin-token"
curl.exe -H "X-Alpha-Token: $env:ALPHA_ADMIN_TOKEN" http://localhost:8000/alpha/readiness
```

The response should report `ready: true`.

## Run Alpha Smoke Script

Use two tester tokens to verify isolation:

```powershell
$env:TESTER_A_TOKEN = "replace-with-tester-a-token"
$env:TESTER_B_TOKEN = "replace-with-tester-b-token"
python scripts/alpha-smoke-test.py `
  --base-url http://localhost:8000 `
  --admin-token $env:ALPHA_ADMIN_TOKEN `
  --tester-a-token $env:TESTER_A_TOKEN `
  --tester-b-token $env:TESTER_B_TOKEN
```

Expected result:

```text
PASS health
PASS alpha readiness
PASS onboarding
PASS demo project ...
PASS tester project list
PASS tester isolation
PASS export download
Alpha smoke test passed.
```

## Generate Demo Manually

```powershell
curl.exe -X POST `
  -H "Content-Type: application/json" `
  -H "X-Alpha-Token: $env:TESTER_A_TOKEN" `
  http://localhost:8000/demo/create-full-project
```

Open the web app:

```text
http://localhost:3000
```

## Download Export

The alpha smoke script prints and verifies the demo export path indirectly. To test manually, first get an export id from the project response or API, then run:

```powershell
curl.exe -L `
  -H "X-Alpha-Token: $env:TESTER_A_TOKEN" `
  -o alpha-export.zip `
  http://localhost:8000/exports/replace-with-export-id/download
```

Confirm the file exists:

```powershell
Get-Item .\alpha-export.zip
```

## Inspect Logs

```powershell
docker compose --env-file .env.alpha logs --tail 200 api
docker compose --env-file .env.alpha logs --tail 200 worker
docker compose --env-file .env.alpha logs --tail 200 web
docker compose --env-file .env.alpha ps
```

Look for:

- Failed jobs.
- Provider errors.
- Auth failures.
- Export failures.
- Unexpected stack traces.

Do not paste secrets into bug reports.

## Stop Stack

Stop services without deleting data:

```powershell
docker compose --env-file .env.alpha down
```

Emergency stop including containers and network:

```powershell
docker compose --env-file .env.alpha down --remove-orphans
```

Do not remove volumes during alpha unless you have backed up Postgres and MinIO data.
