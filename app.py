# app.py
from flask import Flask, render_template
from backend import get_system_overview, get_network_overview


def create_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="dev-change-me")

    @app.route("/")
    def index():
        # 你可以改成自己的首页模板
        return render_template("index.html")

    @app.route("/system")
    def system():
        info = get_system_overview()
        return render_template("system.html", info=info)

    @app.route("/files")
    def files():
        # 先占位，之后再做文件管理器
        return render_template("files.html")

    @app.route("/network")
    def network():
        # ★ 关键：这里给模板传 info，不然就 UndefinedError
        info = get_network_overview()
        return render_template("network.html", info=info)

    return app


if __name__ == "__main__":
    app = create_app()
    # Windows 上开在 0.0.0.0，方便局域网访问
    app.run(host="0.0.0.0", port=8000, debug=True)
