import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";

const health = {
  status: "ok",
  service: "tribuna-api",
  version: "0.1.0",
  environment: "development",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("App health status", () => {
  it("renders loading while the API request is pending", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => undefined)),
    );
    render(<App />);
    expect(screen.getByText("Checking API availability…")).toBeInTheDocument();
  });

  it("renders typed API details when healthy", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(health), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    render(<App />);

    expect(await screen.findByText("API available")).toBeInTheDocument();
    expect(screen.getByText("tribuna-api")).toBeInTheDocument();
    expect(screen.getByText("0.1.0")).toBeInTheDocument();
    expect(screen.getByText("development")).toBeInTheDocument();
  });

  it("renders an unavailable state for a non-success response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(null, { status: 503 }))),
    );
    render(<App />);

    expect(await screen.findByText("API unavailable")).toBeInTheDocument();
    expect(screen.getByText("API returned HTTP 503")).toBeInTheDocument();
  });

  it("retries after a network failure", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Network request failed"))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(health), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    vi.stubGlobal("fetch", fetchMock);
    render(<App />);

    await userEvent.click(
      await screen.findByRole("button", { name: "Retry connection" }),
    );

    expect(await screen.findByText("API available")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
