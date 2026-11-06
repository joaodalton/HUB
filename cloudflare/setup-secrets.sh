#!/bin/bash
# Configura secrets do Worker a partir do .env do backend.
# Rode: cd cloudflare && bash setup-secrets.sh

ENV_FILE="../backend/.env"

KEYS=(
  DATABASE_URL
  SECRET_KEY
  SECRET_ENCRYPTION_KEY
  GOOGLE_OAUTH_CLIENT_ID
  GOOGLE_OAUTH_CLIENT_SECRET
  GOOGLE_OAUTH_REDIRECT_URI
  FRONTEND_URL
  MARKETING_URL
  SENTRY_DSN
  RESEND_API_KEY
  EMAIL_FROM
  ASAAS_API_BASE_URL
  ASAAS_WEBHOOK_TOKEN
  PLATFORM_ASAAS_API_KEY
  PLATFORM_ASAAS_API_BASE_URL
  PLATFORM_ASAAS_WEBHOOK_TOKEN
  STORAGE_PROVIDER
  OBJECT_STORAGE_ENDPOINT
  OBJECT_STORAGE_BUCKET
  OBJECT_STORAGE_ACCESS_KEY_ID
  OBJECT_STORAGE_SECRET_ACCESS_KEY
  OBJECT_STORAGE_REGION
  NEON_API_KEY
  NEON_PROJECT_ID_DEV
  NEON_PROJECT_ID_PROD
  DATA_PROVIDER
  SENTRY_ENVIRONMENT
)

for KEY in "${KEYS[@]}"; do
  VALUE=$(grep "^${KEY}=" "$ENV_FILE" | head -1 | cut -d= -f2-)
  if [ -n "$VALUE" ]; then
    echo "$VALUE" | npx wrangler secret put "$KEY"
    echo "  ✓ $KEY"
  else
    echo "  ⊘ $KEY (vazio, pulando)"
  fi
done

echo ""
echo "Secrets configurados. Rode: npx wrangler deploy"
