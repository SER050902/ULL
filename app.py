from flask import Flask, render_template

def create_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="dev-change-me",
        # 未来要加的配置在这放钩子，如：
        # FILE_ROOT="data",
        # MAX_CONTENT_LENGTH=512 * 1024 * 1024,
    )

    # 首页：先渲染一个空壳，后面再填内容区块
    @app.route("/")
    def index():
        return render_template("base.html")

    # 预留：系统信息页（以后把真实数据塞进来）
    @app.route("/system")
    def system():
        return render_template("base.html")

    # 预留：文件页（以后做成文件管理器）
    @app.route("/files")
    def files():
        return render_template("base.html")

    # 预留：网络信息（公网 IP、本机各网卡 IP）
    @app.route("/network")
    def network():
        return render_template("base.html")

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
