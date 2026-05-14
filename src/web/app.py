"""Flask API and basic HTML page for the TER network digital twin PoC."""

from __future__ import annotations

import argparse

from flask import Flask, jsonify, render_template, request

from src.twin.config import AppConfig
from src.twin.service import TwinService


def create_app(service: TwinService | None = None, config: AppConfig | None = None) -> Flask:
    """Create the Flask app bound to a twin service instance."""

    app = Flask(__name__, template_folder="templates")
    app.config["TWIN_SERVICE"] = service or TwinService(config or AppConfig())

    def get_service() -> TwinService:
        return app.config["TWIN_SERVICE"]

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.get("/topology")
    def topology_page() -> str:
        return render_template("topology.html")

    @app.get("/api/health")
    def api_health():
        return jsonify(get_service().health())

    @app.get("/api/state")
    def api_state():
        return jsonify(get_service().get_state())

    @app.get("/api/topology")
    def api_topology():
        return jsonify(get_service().get_topology())

    @app.get("/api/events")
    def api_events():
        limit = request.args.get("limit", default=20, type=int)
        return jsonify(get_service().get_events(limit=limit))

    @app.get("/api/anomalies")
    def api_anomalies():
        limit = request.args.get("limit", default=20, type=int)
        return jsonify(get_service().get_anomalies(limit=limit))

    @app.get("/api/fidelity")
    def api_fidelity():
        return jsonify(get_service().get_fidelity())

    return app


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the Flask app."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--sync-on-start", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the Flask app."""

    args = parse_args(argv)
    config = AppConfig()
    service = TwinService(config)
    if args.sync_on_start:
        service.start()

    app = create_app(service=service, config=config)
    host = args.host or config.web_host
    port = args.port or config.web_port
    app.run(host=host, port=port, debug=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
