import { Container } from "@cloudflare/containers";

export class HubBackend extends Container {
	defaultPort = 8000;
	sleepAfter = "30m";

	override get envVars(): Record<string, string> {
		const env = this.env as Record<string, string>;
		const keys = [
			"DATABASE_URL",
			"SECRET_KEY",
			"SECRET_ENCRYPTION_KEY",
			"GOOGLE_OAUTH_CLIENT_ID",
			"GOOGLE_OAUTH_CLIENT_SECRET",
			"GOOGLE_OAUTH_REDIRECT_URI",
			"FRONTEND_URL",
			"MARKETING_URL",
			"SENTRY_DSN",
			"SENTRY_ENVIRONMENT",
			"RESEND_API_KEY",
			"EMAIL_FROM",
			"ASAAS_API_BASE_URL",
			"PLATFORM_ASAAS_API_KEY",
			"PLATFORM_ASAAS_API_BASE_URL",
			"PLATFORM_ASAAS_WEBHOOK_TOKEN",
			"ASAAS_WEBHOOK_TOKEN",
			"STORAGE_PROVIDER",
			"OBJECT_STORAGE_ENDPOINT",
			"OBJECT_STORAGE_BUCKET",
			"OBJECT_STORAGE_ACCESS_KEY_ID",
			"OBJECT_STORAGE_SECRET_ACCESS_KEY",
			"OBJECT_STORAGE_REGION",
			"META_APP_SECRET",
			"META_WEBHOOK_VERIFY_TOKEN",
			"NEON_API_KEY",
			"NEON_PROJECT_ID_DEV",
			"NEON_PROJECT_ID_PROD",
			"DATA_PROVIDER",
		];
		const vars: Record<string, string> = {
			FLASK_DEBUG: "false",
			API_PORT: "8000",
		};
		for (const k of keys) {
			if (env[k]) vars[k] = env[k];
		}
		return vars;
	}
}

interface Env {
	HUB_BACKEND: DurableObjectNamespace;
	[key: string]: unknown;
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const id = env.HUB_BACKEND.idFromName("main");
		const stub = env.HUB_BACKEND.get(id);
		return stub.fetch(request);
	},
};
