$envFile = "..\backend\.env"
$keys = @(
  "DATABASE_URL"
  "SECRET_KEY"
  "SECRET_ENCRYPTION_KEY"
  "GOOGLE_OAUTH_CLIENT_ID"
  "GOOGLE_OAUTH_CLIENT_SECRET"
  "GOOGLE_OAUTH_REDIRECT_URI"
  "FRONTEND_URL"
  "MARKETING_URL"
  "SENTRY_DSN"
  "RESEND_API_KEY"
  "EMAIL_FROM"
  "ASAAS_API_BASE_URL"
  "ASAAS_WEBHOOK_TOKEN"
  "PLATFORM_ASAAS_API_KEY"
  "PLATFORM_ASAAS_API_BASE_URL"
  "PLATFORM_ASAAS_WEBHOOK_TOKEN"
  "STORAGE_PROVIDER"
  "OBJECT_STORAGE_ENDPOINT"
  "OBJECT_STORAGE_BUCKET"
  "OBJECT_STORAGE_ACCESS_KEY_ID"
  "OBJECT_STORAGE_SECRET_ACCESS_KEY"
  "OBJECT_STORAGE_REGION"
  "NEON_API_KEY"
  "NEON_PROJECT_ID_DEV"
  "NEON_PROJECT_ID_PROD"
  "DATA_PROVIDER"
  "SENTRY_ENVIRONMENT"
)

$lines = Get-Content $envFile -Encoding utf8
foreach ($key in $keys) {
  $match = $lines | Where-Object { $_ -match "^$key=" } | Select-Object -First 1
  if ($match) {
    $value = $match.Substring($key.Length + 1)
    if ($value) {
      $value | npx wrangler secret put $key
      Write-Host "  ok $key"
    } else {
      Write-Host "  skip $key (vazio)"
    }
  } else {
    Write-Host "  skip $key (nao encontrado)"
  }
}

Write-Host ""
Write-Host "Secrets configurados. Rode: npx wrangler deploy"
