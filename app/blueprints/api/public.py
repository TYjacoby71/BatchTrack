from flask import Blueprint, jsonify, make_response
from datetime import datetime, timezone
from app.extensions import limiter

public_api = Blueprint("public_api", __name__)

@public_api.route("/api/server-time", methods=["GET"])
@limiter.exempt
def server_time():
    ts = datetime.now(timezone.utc).isoformat()
    resp = make_response(jsonify({"server_time": ts}))
    resp.headers["Cache-Control"] = "no-store"
    return resp