from flask import Flask, render_template
from backend import get_system_overview   # ← 加这一行

def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="dev-change-me",
    )

    @app.route("/")
    def index():
        # 有 index.html 就渲染它；没有就先用 base.html 占位
        return render_template("index.html")  # 或者 "base.html"

    @app.route("/system")
    def system():
        info = get_system_overview()
        return render_template("system.html", info=info)

    @app.route("/files")
    def files():
        return render_template("files.html")  # 至少先放个占位模板

    @app.route("/network")
    def network():
        return render_template("base.html")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
