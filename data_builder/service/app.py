from __future__ import annotations

import os

from flask import Flask, jsonify, redirect, render_template_string, request, url_for

from .jobs import get_job, job_to_dict, list_jobs, read_job_log_tail, start_job_from_command


INDEX_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Data Builder Service</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; }
      .row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
      input[type=text] { width: min(980px, 100%); padding: 10px 12px; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono"; }
      button { padding: 10px 12px; cursor: pointer; }
      code { background: #f4f4f5; padding: 2px 6px; border-radius: 6px; }
      pre { background: #0b1020; color: #e6edf3; padding: 12px; border-radius: 10px; overflow: auto; }
      table { width: 100%; border-collapse: collapse; margin-top: 14px; }
      th, td { border-bottom: 1px solid #e5e7eb; padding: 8px 6px; text-align: left; vertical-align: top; }
      .muted { color: #6b7280; }
      .pill { padding: 2px 8px; border-radius: 999px; font-size: 12px; display: inline-block; }
      .queued { background: #eef2ff; color: #3730a3; }
      .running { background: #ecfeff; color: #155e75; }
      .finished { background: #ecfdf5; color: #065f46; }
      .failed { background: #fef2f2; color: #991b1b; }
    </style>
  </head>
  <body>
    <h2>Data Builder Service</h2>
    <p class="muted">
      This service runs on port <code>{{port}}</code>. It will not run any scripts unless you click “Run”.
    </p>
    <p class="muted">
      Builder DB: <code>{{builder_db}}</code>
    </p>

    {% if error %}
      <p style="color:#991b1b;"><strong>Error:</strong> {{error}}</p>
    {% endif %}

    <form method="post" action="{{ url_for('run_command') }}">
      <div class="row">
        <input type="text" name="command" value="{{default_command}}" />
        <button type="submit">Run</button>
      </div>
      <p class="muted">
        Allowed forms: <code>python3 data_builder/…</code> or <code>python3 -m data_builder.…</code>
      </p>
    </form>

    <h3>Recent runs</h3>
    <table>
      <thead>
        <tr>
          <th>Job</th>
          <th>Status</th>
          <th>Command</th>
          <th>Log</th>
        </tr>
      </thead>
      <tbody>
        {% for j in jobs %}
          <tr>
            <td><a href="{{ url_for('job_detail', job_id=j.id) }}"><code>{{j.id}}</code></a></td>
            <td><span class="pill {{j.status}}">{{j.status}}</span></td>
            <td><code>{{ " ".join(j.command) }}</code></td>
            <td><a href="{{ url_for('job_log', job_id=j.id) }}">tail</a></td>
          </tr>
        {% endfor %}
        {% if not jobs %}
          <tr><td colspan="4" class="muted">No runs yet.</td></tr>
        {% endif %}
      </tbody>
    </table>
  </body>
</html>
"""


DETAIL_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Job {{job.id}}</title>
    <style>
      body { font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; margin: 24px; }
      code { background: #f4f4f5; padding: 2px 6px; border-radius: 6px; }
      pre { background: #0b1020; color: #e6edf3; padding: 12px; border-radius: 10px; overflow: auto; }
      .muted { color: #6b7280; }
      a { text-decoration: none; }
    </style>
  </head>
  <body>
    <p><a href="{{ url_for('index') }}">&larr; back</a></p>
    <h2>Job <code>{{job.id}}</code></h2>
    <p><strong>Status:</strong> <code>{{job.status}}</code></p>
    <p><strong>Command:</strong> <code>{{ " ".join(job.command) }}</code></p>
    <p class="muted">pid={{job.pid}} rc={{job.returncode}} created={{job.created_at}}</p>
    {% if job.error %}
      <p style="color:#991b1b;"><strong>Error:</strong> {{job.error}}</p>
    {% endif %}
    <p><a href="{{ url_for('job_log', job_id=job.id) }}">View log tail</a></p>
  </body>
</html>
"""


def create_data_builder_app() -> Flask:
    app = Flask(__name__)
    app.config.update(JSON_SORT_KEYS=False)

    def _builder_db() -> str:
        return (
            os.environ.get("DATA_BUILDER_DATABASE_URL")
            or os.environ.get("DATABASE_URL")
            or "(not set)"
        )

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "service": "data_builder.service"})

    @app.get("/")
    def index():
        default_command = "python3 data_builder/scrapers/tgsc_scraper.py --max-ingredients 30 --max-workers 3"
        return render_template_string(
            INDEX_TEMPLATE,
            jobs=list_jobs(limit=50),
            error=request.args.get("error"),
            default_command=default_command,
            builder_db=_builder_db(),
            port=os.environ.get("DATA_BUILDER_PORT", "5051"),
        )

    @app.post("/run")
    def run_command():
        command = (request.form.get("command") or "").strip()
        if not command:
            return redirect(url_for("index", error="Missing command"))
        try:
            job = start_job_from_command(command)
        except ValueError as exc:
            return redirect(url_for("index", error=str(exc)))
        return redirect(url_for("job_detail", job_id=job.id))

    @app.get("/jobs")
    def jobs_list_json():
        return jsonify({"jobs": [job_to_dict(j) for j in list_jobs(limit=100)]})

    @app.get("/jobs/<job_id>")
    def job_detail(job_id: str):
        job = get_job(job_id)
        if not job:
            return jsonify({"error": "Not found"}), 404
        if request.args.get("format") == "json":
            return jsonify({"job": job_to_dict(job)})
        return render_template_string(DETAIL_TEMPLATE, job=job)

    @app.get("/jobs/<job_id>/log")
    def job_log(job_id: str):
        try:
            max_bytes = int(request.args.get("max_bytes", "64000"))
        except ValueError:
            max_bytes = 64_000
        try:
            tail = read_job_log_tail(job_id, max_bytes=max_bytes)
        except FileNotFoundError:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"job_id": job_id, "tail": tail})

    return app

