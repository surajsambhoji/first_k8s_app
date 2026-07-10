"""Minimal Flask app for practicing Docker + Kubernetes deployment.

Endpoints:
  GET /healthz  -> liveness/readiness probe target
  GET /hello    -> greeting, optionally personalized via ?name=
  GET /count    -> per-pod in-memory request counter
"""
import os
import platform
from datetime import datetime, timezone
from typing import Mapping, Optional

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)

class AppConfig:
    def __init__(self, message: str, environment: str, port: int):
        self.message = message
        self.environment = environment
        self.port = port


def load_config(env: Mapping[str, str]) -> AppConfig:
    """Build an AppConfig from an environment mapping, never raising.

    Falls back to documented defaults for missing or malformed values.
    """
    message = env.get("APP_MESSAGE", "Hello from Kubernetes!")
    environment = env.get("APP_ENV", "development")

    port = 8080
    raw_port = env.get("PORT")
    if raw_port is not None:
        try:
            parsed = int(raw_port)
            if parsed > 0:
                port = parsed
        except (TypeError, ValueError):
            pass

    return AppConfig(message=message, environment=environment, port=port)


def build_hello_message(app_message: str, name: Optional[str]) -> str:
    """Pure function that builds the /hello greeting text."""
    if name is None or name.strip() == "":
        return f"{app_message}!"
    return f"{app_message}, {name.strip()}!"


# Configuration loaded once at process startup.
config = load_config(os.environ)

# Module-level counter state, initialized exactly once per process.
_counter = {"value": 0}


def next_count(counter_ref: dict) -> int:
    """Increment the counter by exactly 1 and return the new value."""
    counter_ref["value"] += 1
    return counter_ref["value"]


_INDEX_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>k8s-app</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --accent: #38bdf8;
      --text: #e2e8f0;
      --muted: #94a3b8;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, Segoe UI, Roboto, sans-serif;
      background: linear-gradient(135deg, var(--bg), #1e1b4b);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }
    .card {
      background: var(--card);
      border-radius: 16px;
      padding: 32px 40px;
      max-width: 560px;
      width: 100%;
      box-shadow: 0 20px 60px rgba(0,0,0,0.35);
      border: 1px solid rgba(148,163,184,0.15);
    }
    h1 {
      margin: 0 0 4px;
      font-size: 1.6rem;
      color: white;
    }
    .subtitle { color: var(--muted); margin-bottom: 24px; font-size: 0.95rem; }
    .badge {
      display: inline-block;
      background: rgba(56,189,248,0.15);
      color: var(--accent);
      padding: 2px 10px;
      border-radius: 999px;
      font-size: 0.75rem;
      font-weight: 600;
      margin-bottom: 20px;
    }
    .links { display: grid; gap: 12px; }
    a.route {
      display: flex;
      justify-content: space-between;
      align-items: center;
      background: rgba(148,163,184,0.08);
      border: 1px solid rgba(148,163,184,0.15);
      border-radius: 10px;
      padding: 14px 16px;
      text-decoration: none;
      color: var(--text);
      transition: background 0.15s ease, transform 0.15s ease;
    }
    a.route:hover {
      background: rgba(56,189,248,0.12);
      transform: translateY(-1px);
    }
    a.route .path { font-family: Consolas, monospace; color: var(--accent); font-weight: 600; }
    a.route .desc { color: var(--muted); font-size: 0.85rem; }
    footer { margin-top: 24px; color: var(--muted); font-size: 0.8rem; text-align: center; }
    code { color: var(--accent); }
  </style>
</head>
<body>
  <div class="card">
    <span class="badge">ENV: {{ environment }}</span>
    <h1>k8s-app</h1>
    <p class="subtitle">A tiny Flask service for practicing Docker &amp; Kubernetes deployment.</p>
    <div class="links">
      <a class="route" href="/healthz">
        <span class="path">/healthz</span>
        <span class="desc">liveness / readiness check</span>
      </a>
      <a class="route" href="/hello?name=Kiro">
        <span class="path">/hello?name=Kiro</span>
        <span class="desc">greeting endpoint</span>
      </a>
      <a class="route" href="/count">
        <span class="path">/count</span>
        <span class="desc">per-pod counter (refresh me)</span>
      </a>
      <a class="route" href="/info">
        <span class="path">/info</span>
        <span class="desc">pod &amp; config details</span>
      </a>
    </div>
    <footer>Serving from pod <code>{{ pod }}</code></footer>
  </div>
</body>
</html>
"""


@app.get("/")
def index():
    """Browser-friendly landing page linking to the API endpoints."""
    pod = os.environ.get("HOSTNAME", "unknown")
    return render_template_string(_INDEX_TEMPLATE, environment=config.environment, pod=pod), 200


@app.get("/info")
def info():
    """Diagnostic endpoint showing loaded config and pod identity.

    Useful for observing how ConfigMap values and per-pod identity differ
    when the app is scaled to multiple replicas in Kubernetes.
    """
    return (
        jsonify(
            message=config.message,
            environment=config.environment,
            port=config.port,
            pod=os.environ.get("HOSTNAME", "unknown"),
            python_version=platform.python_version(),
            server_time_utc=datetime.now(timezone.utc).isoformat(),
        ),
        200,
    )


@app.get("/healthz")
def healthz():
    return jsonify(status="ok"), 200


@app.get("/hello")
def hello():
    name = request.args.get("name")
    return jsonify(message=build_hello_message(config.message, name)), 200


@app.get("/count")
def count():
    new_value = next_count(_counter)
    pod = os.environ.get("HOSTNAME", "unknown")
    return jsonify(count=new_value, pod=pod), 200


@app.get("/favicon.ico")
def favicon():
    # Avoids noisy 404s when testing in a browser.
    return "", 204


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.port)
