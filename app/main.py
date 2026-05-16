from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response

from app.agent_gateway import build_agent_gateway
from app.models import ProgressEvent, RunRequest, RunStatusResponse
from app.settings import settings
from app.storage import store

app = FastAPI(title="GapHunter", version="0.1.0")
gateway = build_agent_gateway(settings.agent_backend, store)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "mode": "live" if settings.live_research_enabled else "demo",
    }


@app.post("/runs", response_model=RunStatusResponse, status_code=202)
def create_run(request: RunRequest) -> RunStatusResponse:
    queued = store.create_queued_run(request)
    if queued.status != "queued":
        return queued

    gateway.start_run(queued.run_id, request)
    return queued


@app.get("/runs/{run_id}", response_model=RunStatusResponse)
def get_run(run_id: str) -> RunStatusResponse:
    result = store.get_status(run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Run not found")
    return result


@app.get("/runs/{run_id}/events", response_model=list[ProgressEvent])
def get_run_events(run_id: str) -> list[ProgressEvent]:
    events = store.get_events(run_id)
    if events is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return events


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
    const stageLabels = {
      queued: "Queued",
      parsing_constraints: "Parsing constraints",
      planning_research: "Planning research",
      researching_jobs: "Researching jobs",
      checking_competitors: "Checking competitors",
      synthesizing_ideas: "Synthesizing ideas",
      critiquing: "Critiquing",
      scoring: "Scoring",
      running: "Running research",
      completed: "Completed",
      failed: "Failed"
    };
    function esc(s) {
      return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");
    }
    function cleanText(value) {
      const parser = document.createElement("textarea");
      let text = String(value ?? "");
      for (let i = 0; i < 3; i += 1) {
        parser.innerHTML = text;
        const decoded = parser.value;
        if (decoded === text) break;
        text = decoded;
      }
      return text.replace(/<[^>]*>/g, "").replace(/\\s+/g, " ").replace(/\\.{4,}/g, "...").trim();
    }
    function display(value) {
      return esc(cleanText(value));
    }
    function renderSources(idea) {
      const evidence = (idea.gap_evidence || []).map((item) => `
        <li><a href="${esc(item.url)}" rel="noreferrer" target="_blank">${display(item.label)}</a>: ${display(item.note)}</li>
      `);
      const urls = (idea.source_urls || []).map((url) => `
        <li><a href="${esc(url)}" rel="noreferrer" target="_blank">${display(url)}</a></li>
      `);
      return [...evidence, ...urls].join("");
    }
    function renderEvents(events) {
      if (!events || events.length === 0) return "";
      return `<ol>${events.map((event) => `
        <li><strong>${display(stageLabels[event.stage] || event.stage)}</strong>: ${display(event.message)}</li>
      `).join("")}</ol>`;
    }
    function renderRun(run) {
      if (run.status === "failed") {
        results.innerHTML = `<p class="error">${display(run.error || "Run failed")}</p>${renderEvents(run.events)}`;
        return;
      }
      if (run.status !== "completed") {
        results.innerHTML = `<p>${display(stageLabels[run.progress] || run.progress || run.status)}</p>${renderEvents(run.events)}`;
        return;
      }
      results.innerHTML = (run.ideas || []).map((idea) => `
        <article>
          <h2>${display(idea.title)}</h2>
          <p>${display(idea.one_liner)}</p>
          <p><strong>Target:</strong> ${display(idea.target_customer)}</p>
          <p><strong>Job:</strong> ${display(idea.job_being_replaced)}</p>
          <p class="score">Research coverage: ${Math.round(idea.research_coverage_score * 100)}%</p>
          <p><strong>Critique:</strong> ${idea.critique.objections.map(display).join(" ")}</p>
          <p><strong>Sources:</strong></p>
          <ul>${renderSources(idea)}</ul>
        </article>
      `).join("");
    }
    async function pollRun(runId) {
      const startedAt = Date.now();
      const timeoutMs = 10 * 60 * 1000;
      const slowMs = 5 * 60 * 1000;
      while (Date.now() - startedAt < timeoutMs) {
        const response = await fetch(`/runs/${encodeURIComponent(runId)}`);
        if (!response.ok) throw new Error(await response.text());
        const run = await response.json();
        if (Date.now() - startedAt > slowMs && run.status !== "completed" && run.status !== "failed") {
          run.progress = "This is taking longer than expected.";
        }
        renderRun(run);
        if (run.status === "completed" || run.status === "failed") return;
        await new Promise((resolve) => setTimeout(resolve, 2000));
      }
      throw new Error("Run is taking longer than expected.");
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
        renderRun(run);
        await pollRun(run.run_id);
      } catch (error) {
        results.innerHTML = `<p class="error">${display(error.message)}</p>`;
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
