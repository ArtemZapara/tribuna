import { useHealth } from "./api/useHealth";
import "./styles.css";

export function App() {
  const { state, retry } = useHealth();

  return (
    <div className="app-shell">
      <header className="brand">
        <span className="brand-mark" aria-hidden="true">
          T
        </span>
        <div>
          <p className="eyebrow">Football analysis workspace</p>
          <h1>Tribuna</h1>
        </div>
      </header>

      <main>
        <section className="status-card" aria-labelledby="api-status-title">
          <div>
            <p className="eyebrow">System status</p>
            <h2 id="api-status-title">Analysis API</h2>
          </div>

          {state.status === "loading" && (
            <div className="status-row" role="status">
              <span
                className="indicator indicator-loading"
                aria-hidden="true"
              />
              <p>Checking API availability…</p>
            </div>
          )}

          {state.status === "healthy" && (
            <div className="health-details" role="status">
              <div className="status-row">
                <span
                  className="indicator indicator-healthy"
                  aria-hidden="true"
                />
                <p>API available</p>
              </div>
              <dl>
                <div>
                  <dt>Service</dt>
                  <dd>{state.data.service}</dd>
                </div>
                <div>
                  <dt>Version</dt>
                  <dd>{state.data.version}</dd>
                </div>
                <div>
                  <dt>Environment</dt>
                  <dd>{state.data.environment}</dd>
                </div>
              </dl>
            </div>
          )}

          {state.status === "unavailable" && (
            <div className="health-details" role="alert">
              <div className="status-row">
                <span
                  className="indicator indicator-error"
                  aria-hidden="true"
                />
                <p>API unavailable</p>
              </div>
              <p className="reason">{state.reason}</p>
              <button type="button" onClick={retry}>
                Retry connection
              </button>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
