from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.models import RunRequest, RunStatusResponse
from app.pipeline import run_pipeline
from app.settings import settings
from app.storage import store

app = FastAPI(title="GapHunter", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "live" if settings.live_research_enabled else "demo",
    }


@app.post("/runs", response_model=RunStatusResponse)
def create_run(request: RunRequest) -> RunStatusResponse:
    queued = store.create_queued_run(request)
    if queued.status != "queued":
        return queued

    try:
        store.mark_running(queued.run_id)
        store.append_event(queued.run_id, "running", "Research pipeline started.")
        result = run_pipeline(request)
        return store.complete_with_result(queued.run_id, result)
    except Exception as exc:
        return store.fail_with_error(queued.run_id, str(exc))


@app.get("/runs/{run_id}", response_model=RunStatusResponse)
def get_run(run_id: str) -> RunStatusResponse:
    result = store.get_status(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GapHunter</title>
  <style>
    :root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f6f8fb; color: #111827; }
    main { max-width: 1040px; margin: 0 auto; padding: 40px 20px; }
    header { display: flex; align-items: center; gap: 16px; margin-bottom: 32px; }
    img { width: 56px; height: 56px; }
    h1 { font-size: 34px; line-height: 1.1; margin: 0; letter-spacing: 0; }
    p { color: #475569; line-height: 1.6; }
    form { display: grid; gap: 12px; margin: 24px 0; }
    textarea { min-height: 132px; resize: vertical; padding: 14px; border: 1px solid #cbd5e1; border-radius: 8px; font: inherit; }
    button { width: fit-content; border: 0; border-radius: 8px; background: #0f766e; color: white; padding: 12px 18px; font-weight: 700; cursor: pointer; }
    button:disabled { opacity: .7; cursor: wait; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-top: 24px; }
    article { background: white; border: 1px solid #e2e8f0; border-radius: 8px; padding: 18px; }
    h2 { font-size: 18px; margin: 0 0 8px; }
    .score { color: #0f766e; font-weight: 700; }
    .error { color: #b91c1c; }
  </style>
</head>
<body>
  <main>
    <header>
      <img src="/assets/logo.svg" alt="GapHunter logo">
      <div>
        <h1>GapHunter</h1>
        <p>Founder-grade market gap research with source-backed briefs and adversarial critique.</p>
      </div>
    </header>
    <form id="run-form">
      <textarea id="prompt" aria-label="Constraint prompt">Swiss B2B workflows with digital inputs, high manual complexity, and no fintech.</textarea>
      <button id="submit" type="submit">Run Research</button>
    </form>
    <section id="results" class="grid"></section>
  </main>
  <script>
    const form = document.getElementById("run-form");
    const button = document.getElementById("submit");
    const results = document.getElementById("results");
    function esc(s) {
      return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
    }
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      button.disabled = true;
      results.innerHTML = "";
      try {
        const response = await fetch("/runs", {
          method: "POST",
          headers: {"content-type": "application/json"},
          body: JSON.stringify({prompt: document.getElementById("prompt").value})
        });
        if (!response.ok) throw new Error(await response.text());
        const run = await response.json();
        results.innerHTML = run.ideas.map((idea) => `
          <article>
            <h2>${esc(idea.title)}</h2>
            <p>${esc(idea.one_liner)}</p>
            <p><strong>Target:</strong> ${esc(idea.target_customer)}</p>
            <p><strong>Job:</strong> ${esc(idea.job_being_replaced)}</p>
            <p class="score">Research coverage: ${Math.round(idea.research_coverage_score * 100)}%</p>
            <p><strong>Critique:</strong> ${idea.critique.objections.map(esc).join(" ")}</p>
          </article>
        `).join("");
      } catch (error) {
        results.innerHTML = `<p class="error">${esc(error.message)}</p>`;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


@app.get("/assets/logo.svg")
def logo() -> Response:
    with open("assets/logo.svg", encoding="utf-8") as logo_file:
        return Response(content=logo_file.read(), media_type="image/svg+xml")
