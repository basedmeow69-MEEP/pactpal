"""FastAPI Server for PactPal (PayPal AI Hackathon - Autonomous Clearinghouse & Dispute Courtroom)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response

from src.backend.pactpal_engine import PactPalClearinghouseEngine

app = FastAPI(
    title="PactPal - Autonomous Agent-to-Agent Clearinghouse, SLA Escrow & Sandbox Dispute Courtroom",
    version="1.11.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = PactPalClearinghouseEngine()
FRONTEND_HTML = Path("src/frontend/index.html")


@app.get("/", response_class=HTMLResponse)
async def serve_command_center() -> HTMLResponse:
    if FRONTEND_HTML.exists():
        return HTMLResponse(FRONTEND_HTML.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>PactPal Clearinghouse Running</h1>")


@app.get("/api/scenarios")
async def list_scenarios() -> JSONResponse:
    return JSONResponse(engine.get_scenarios())


@app.post("/api/execute-pact")
async def execute_pact(
    request: Request,
    scenario_key: str = Form("b2b_gpu_inference_cluster"),
    sla_outcome_mode: str = Form("amber_dispute"),
    override_budget_cap_usd: float | None = Form(None),
    run_id: str | None = Form(None),
) -> JSONResponse:
    result: dict[str, Any] = engine.execute_pact_lifecycle(
        scenario_key=scenario_key,
        sla_outcome_mode=sla_outcome_mode,
        override_budget_cap_usd=override_budget_cap_usd,
        run_id=run_id,
        return_base_url=str(request.base_url),
    )
    return JSONResponse(result)


@app.get("/approved", response_class=HTMLResponse)
async def buyer_returned(pact: str = "", cancelled: str = "") -> HTMLResponse:
    """PayPal return_url: tell the PactPal tab the buyer finished, then let the buyer close this tab."""
    outcome = "cancelled" if cancelled else "approved"
    payload = json.dumps({"outcome": outcome, "pact": pact[:120]}).replace("<", "\\u003c")
    message = "Payment cancelled." if cancelled else "Payment approved."
    return HTMLResponse(f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><title>PactPal</title></head>
<body style="background:#020617;color:#e2e8f0;font-family:sans-serif;display:grid;place-items:center;height:100vh;margin:0">
<div style="text-align:center"><h1 style="color:#34d399">{message}</h1>
<p>PactPal is continuing the pact in its own tab. You can close this one.</p></div>
<script>
  try {{ new BroadcastChannel("pactpal").postMessage({payload}); }} catch (e) {{}}
  setTimeout(() => window.close(), 1500);
</script></body></html>""")


RECORDED_RUNS = Path("vault/recorded_runs")


@app.get("/api/recorded-runs")
async def list_recorded_runs() -> JSONResponse:
    """Real live-Sandbox runs saved for judges who run PactPal without PayPal credentials."""
    return JSONResponse(sorted(p.stem for p in RECORDED_RUNS.glob("*.json")))


@app.get("/api/recorded-runs/{name}")
async def get_recorded_run(name: str) -> JSONResponse:
    path = RECORDED_RUNS / f"{name}.json"
    if not name.replace("_", "").isalnum() or not path.exists():
        return JSONResponse({"error": "unknown recorded run"}, status_code=404)
    return JSONResponse(json.loads(path.read_text(encoding="utf-8")))


@app.get("/api/mcp/tools")
async def list_paypal_agent_toolkit_mcp_tools() -> JSONResponse:
    """Expose @paypal/agent-toolkit v1.11.0 + PactPal Escrow MCP tools for judge inspection."""
    return JSONResponse(
        {
            "toolkit_version": "@paypal/agent-toolkit v1.11.0 + APIMatic Typed Bindings",
            "environment": "SANDBOX (https://api-m.sandbox.paypal.com)",
            "tools": [
                "create_invoice",
                "create_conditional_rules_for_invoice",
                "generate_invoice_qr_code",
                "create_order",
                "pay_order",
                "create_shipment_tracking",
                "create_batch_payout",
                "get_dispute",
                "provide_dispute_evidence",
                "make_dispute_offer",
                "accept_dispute_claim",
            ],
        }
    )


@app.get("/api/qr/{code_id}.svg")
async def serve_invoice_qr_svg(code_id: str) -> Response:
    """Render a deterministic scannable-style SVG QR badge for PayPal Invoices v2."""
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 220 220">
      <rect width="220" height="220" rx="14" fill="#0f172a" stroke="#38bdf8" stroke-width="2"/>
      <rect x="20" y="20" width="50" height="50" fill="none" stroke="#38bdf8" stroke-width="6"/>
      <rect x="34" y="34" width="22" height="22" fill="#38bdf8"/>
      <rect x="150" y="20" width="50" height="50" fill="none" stroke="#38bdf8" stroke-width="6"/>
      <rect x="164" y="34" width="22" height="22" fill="#38bdf8"/>
      <rect x="20" y="150" width="50" height="50" fill="none" stroke="#38bdf8" stroke-width="6"/>
      <rect x="34" y="164" width="22" height="22" fill="#38bdf8"/>
      <rect x="88" y="88" width="44" height="44" rx="6" fill="#0070ba"/>
      <text x="110" y="115" text-anchor="middle" fill="#ffffff" font-family="sans-serif" font-size="14" font-weight="bold">PP</text>
      <text x="110" y="206" text-anchor="middle" fill="#94a3b8" font-family="monospace" font-size="10">INV-QR :: {code_id[:10]}</text>
    </svg>"""
    return Response(content=svg, media_type="image/svg+xml")
