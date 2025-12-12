# app.py
from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from backend import (
    get_system_overview, get_network_overview,
    list_dir, delete_path, make_dir, rename_path, save_upload, build_breadcrumbs, _safe_join
)
import os
import config

def create_app():
    app = Flask(__name__)
    app.config.update(SECRET_KEY="dev-change-me")
    app.config["FILE_ROOT"] = getattr(config, "FILE_ROOT", os.path.abspath("."))

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/system")
    def system():
        info = get_system_overview()
        return render_template("system.html", info=info)

    # ✅ 文件浏览
    @app.route("/files")
    def files():
        path = request.args.get("path", "")
        try:
            items = list_dir(app.config["FILE_ROOT"], path)
            crumbs = build_breadcrumbs(path)
            return render_template("files.html", items=items, path=path, crumbs=crumbs)
        except Exception as e:
            flash(f"打开目录失败：{e}", "danger")
            return render_template("files.html", items=[], path="", crumbs=[])

    # ✅ 下载
    @app.route("/files/download")
    def files_download():
        path = request.args.get("path", "")
        p = _safe_join(app.config["FILE_ROOT"], path)
        if not p.exists() or p.is_dir():
            flash("文件不存在或是目录，无法下载。", "warning")
            return redirect(url_for("files", path=os.path.dirname(path).replace("\\", "/")))
        return send_file(str(p), as_attachment=True, download_name=p.name)

    # ✅ 上传
    @app.route("/files/upload", methods=["POST"])
    def files_upload():
        path = request.form.get("path", "")
        f = request.files.get("file")
        if not f:
            flash("没有选择文件。", "warning")
            return redirect(url_for("files", path=path))
        try:
            name = save_upload(app.config["FILE_ROOT"], path, f)
            flash(f"上传成功：{name}", "success")
        except Exception as e:
            flash(f"上传失败：{e}", "danger")
        return redirect(url_for("files", path=path))

    # ✅ 新建文件夹
    @app.route("/files/mkdir", methods=["POST"])
    def files_mkdir():
        path = request.form.get("path", "")
        name = request.form.get("name", "").strip()
        if not name:
            flash("文件夹名不能为空。", "warning")
            return redirect(url_for("files", path=path))
        try:
            make_dir(app.config["FILE_ROOT"], path, name)
            flash(f"已创建文件夹：{name}", "success")
        except Exception as e:
            flash(f"创建失败：{e}", "danger")
        return redirect(url_for("files", path=path))

    # ✅ 删除（文件/空文件夹）
    @app.route("/files/delete", methods=["POST"])
    def files_delete():
        path = request.form.get("path", "")
        cur = request.form.get("cur", "")
        try:
            delete_path(app.config["FILE_ROOT"], path)
            flash("删除成功。", "success")
        except Exception as e:
            flash(f"删除失败：{e}", "danger")
        return redirect(url_for("files", path=cur))

    # ✅ 重命名
    @app.route("/files/rename", methods=["POST"])
    def files_rename():
        path = request.form.get("path", "")
        cur = request.form.get("cur", "")
        new_name = request.form.get("new_name", "").strip()
        if not new_name:
            flash("新名字不能为空。", "warning")
            return redirect(url_for("files", path=cur))
        try:
            rename_path(app.config["FILE_ROOT"], path, new_name)
            flash("重命名成功。", "success")
        except Exception as e:
            flash(f"重命名失败：{e}", "danger")
        return redirect(url_for("files", path=cur))

    @app.route("/network")
    def network():
        info = get_network_overview()
        return render_template("network.html", info=info)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=8000, debug=True)
