import { Container, getContainer } from "@cloudflare/containers";

export class HubBackendContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "10m";
}

interface Env {
  HUB_BACKEND_CONTAINER: DurableObjectNamespace<HubBackendContainer>;
}

export default {
  async fetch(request: Request, env: Env) {
    const container = getContainer(env.HUB_BACKEND_CONTAINER);
    return container.fetch(request);
  },
};
