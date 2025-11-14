try:
    from gevent import monkey  # type: ignore

    monkey.patch_all()
except Exception:
    # gevent may not be installed in local/dev environments
    pass

from app import create_app

app = create_app()


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=bool(app.config.get('DEBUG')))
