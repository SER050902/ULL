from flask import Flask, render_template
from backend import get_system_overview  # 只导入函数，启动期就能发现问题

def create_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="dev-change-me")

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/system")
    def system():
        info = get_system_overview()
        return render_template("system.html", info=info)

    @app.route("/files")
    def files():
        return render_template("files.html")

    @app.route("/network")
    def network():
        return render_template("network.html")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
