import { useCallback, useEffect, useState } from "react";

import type { components } from "./schema";
import { apiClient } from "./client";

type HealthResponse = components["schemas"]["HealthResponse"];

export type HealthState =
  | { status: "loading" }
  | { status: "healthy"; data: HealthResponse }
  | { status: "unavailable"; reason: string };

export function useHealth(): { state: HealthState; retry: () => void } {
  const [state, setState] = useState<HealthState>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    async function checkHealth(): Promise<void> {
      setState({ status: "loading" });
      try {
        const { data, error, response } = await apiClient.GET(
          "/api/v1/health",
          {
            signal: controller.signal,
          },
        );
        if (!response.ok || error || !data) {
          throw new Error(`API returned HTTP ${response.status}`);
        }
        setState({ status: "healthy", data });
      } catch (error: unknown) {
        if (controller.signal.aborted) return;
        const reason =
          error instanceof Error ? error.message : "Request failed";
        setState({ status: "unavailable", reason });
      }
    }

    void checkHealth();
    return () => controller.abort();
  }, [attempt]);

  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return { state, retry };
}
