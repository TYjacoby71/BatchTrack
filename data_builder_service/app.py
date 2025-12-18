from __future__ import annotations

from flask import Flask, jsonify, request

from .jobs import job_to_dict, list_jobs, read_job_log_tail, start_job


def create_data_builder_app() -> Flask:
    app = Flask(__name__)
    # This is an internal service; keep it simple and stateless.
    app.config.update(
        JSON_SORT_KEYS=False,
    )

    @app.get("/health")
    def health():
        return jsonify({"ok": True, "service": "data_builder_service"})

    @app.get("/jobs")
    def jobs_list():
        try:
            limit = int(request.args.get("limit", "50"))
        except ValueError:
            limit = 50
        return jsonify({"jobs": [job_to_dict(j) for j in list_jobs(limit=limit)]})

    @app.post("/jobs")
    def jobs_start():
        payload = request.get_json(silent=True) or {}
        name = payload.get("name")
        args = payload.get("args") or {}
        if not isinstance(name, str) or not name:
            return jsonify({"error": "Missing job name"}), 400
        if not isinstance(args, dict):
            return jsonify({"error": "args must be an object"}), 400
        try:
            job = start_job(name=name, args=args)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"job": job_to_dict(job)}), 202

    @app.get("/jobs/<job_id>")
    def jobs_get(job_id: str):
        from .jobs import get_job

        job = get_job(job_id)
        if not job:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"job": job_to_dict(job)})

    @app.get("/jobs/<job_id>/log")
    def jobs_log(job_id: str):
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

