"""CunDrop — 基于 Cloudflare R2 的个人网盘/图床。"""
import os
import secrets
import time
import uuid
from datetime import date
from functools import wraps

from flask import (
    Flask,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

import db
from r2 import R2Client

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))
APP_PASSWORD_HASH = generate_password_hash(os.environ.get("APP_PASSWORD", "change-me"))

_r2 = None


def r2():
    global _r2
    if _r2 is None:
        _r2 = R2Client()
    return _r2


db.init_db()


@app.template_filter("filesize")
def filesize_filter(n):
    n = int(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("authed"):
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "未登录"}), 401
            return redirect(url_for("login", next=request.path))
        return f(*a, **kw)

    return wrapper


# ---------- 页面 ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        pwd = request.form.get("password", "")
        if check_password_hash(APP_PASSWORD_HASH, pwd):
            session["authed"] = True
            return redirect(request.args.get("next") or url_for("index"))
        return render_template("login.html", error="密码不正确"), 401
    if session.get("authed"):
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("dashboard.html")


@app.route("/f/<token>", methods=["GET", "POST"])
def share_page(token):
    """公开分享页：无需登录，可设密码和有效期。"""
    s = db.get_share(token)
    if not s:
        abort(404)
    if s["expires_at"] and s["expires_at"] < time.time():
        abort(410)
    if s["password_hash"]:
        if request.method == "POST":
            if check_password_hash(s["password_hash"], request.form.get("password", "")):
                session[f"share_{token}"] = True
                return redirect(request.url)
            return render_template("share.html", need_password=True, error="密码不正确")
        if not session.get(f"share_{token}"):
            return render_template("share.html", need_password=True)
    if request.method == "POST":
        return redirect(request.url)
    db.bump_views(token)
    mime = s["mime"] or ""
    kind = (
        "video" if mime.startswith("video")
        else "image" if mime.startswith("image")
        else "audio" if mime.startswith("audio")
        else "file"
    )
    stream_url = r2().presigned_get(s["r2_key"], expires=6 * 3600)
    dl_url = url_for("share_download", token=token)
    return render_template(
        "share.html", share=s, kind=kind, stream_url=stream_url, dl_url=dl_url
    )


@app.route("/f/<token>/download")
def share_download(token):
    s = db.get_share(token)
    if not s:
        abort(404)
    if s["expires_at"] and s["expires_at"] < time.time():
        abort(410)
    if s["password_hash"] and not session.get(f"share_{token}"):
        abort(403)
    url = r2().presigned_get(s["r2_key"], filename=s["filename"], download=True)
    return redirect(url)


# ---------- API ----------
@app.route("/api/me")
@login_required
def api_me():
    return jsonify({"ok": True})


@app.route("/api/r2/ping")
@login_required
def api_r2_ping():
    try:
        r2().ping()
        return jsonify({"ok": True, "bucket": os.environ.get("R2_BUCKET")})
    except Exception as e:
        return jsonify({"ok": False, "error": f"R2 连接失败：{e}"})


@app.route("/api/files")
@login_required
def api_files():
    return jsonify({"ok": True, "files": db.list_files(), "stats": db.stats()})


@app.route("/api/files/init", methods=["POST"])
@login_required
def api_files_init():
    data = request.get_json(force=True)
    filename = (data.get("filename") or "unnamed").strip()[:200]
    size = int(data.get("size") or 0)
    mime = (data.get("mime") or "application/octet-stream")[:100]
    if size <= 0 or size > 5 * 1024**3:
        return jsonify({"ok": False, "error": "文件大小不合法（0 < size ≤ 5GB）"}), 400
    key = f"{date.today().isoformat()}/{uuid.uuid4().hex}_{filename}"
    fid = db.add_file(filename, key, size, mime)
    try:
        url = r2().presigned_put(key, mime)
    except Exception as e:
        return jsonify({"ok": False, "error": f"R2 签名失败：{e}"}), 500
    return jsonify({"ok": True, "file_id": fid, "upload_url": url})


@app.route("/api/files/complete", methods=["POST"])
@login_required
def api_files_complete():
    data = request.get_json(force=True)
    fid = int(data.get("file_id") or 0)
    f = db.get_file(fid)
    if not f:
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    if not r2().head(f["r2_key"]):
        return jsonify({"ok": False, "error": "R2 上找不到该文件，上传可能失败"}), 400
    db.complete_file(fid)
    return jsonify({"ok": True})


@app.route("/api/files/<int:fid>", methods=["DELETE"])
@login_required
def api_files_delete(fid):
    key = db.delete_file(fid)
    if key:
        r2().delete(key)
    return jsonify({"ok": True})


@app.route("/api/shares", methods=["GET"])
@login_required
def api_shares_list():
    return jsonify({"ok": True, "shares": db.list_shares()})


@app.route("/api/shares", methods=["POST"])
@login_required
def api_shares_create():
    data = request.get_json(force=True)
    fid = int(data.get("file_id") or 0)
    if not db.get_file(fid):
        return jsonify({"ok": False, "error": "文件不存在"}), 404
    days = data.get("expires_in_days")
    expires_at = int(time.time() + days * 86400) if days else None
    pwd = (data.get("password") or "").strip()
    token = secrets.token_urlsafe(10)
    db.create_share(
        token, fid,
        generate_password_hash(pwd) if pwd else None,
        expires_at,
    )
    url = url_for("share_page", token=token, _external=True)
    return jsonify({"ok": True, "token": token, "url": url})


@app.route("/api/shares/<token>", methods=["DELETE"])
@login_required
def api_shares_delete(token):
    db.delete_share(token)
    return jsonify({"ok": True})


@app.route("/api/password", methods=["POST"])
@login_required
def api_password():
    global APP_PASSWORD_HASH
    data = request.get_json(force=True)
    old, new = data.get("old", ""), data.get("new", "")
    if not check_password_hash(APP_PASSWORD_HASH, old):
        return jsonify({"ok": False, "error": "原密码不正确"}), 400
    if len(new) < 6:
        return jsonify({"ok": False, "error": "新密码至少 6 位"}), 400
    APP_PASSWORD_HASH = generate_password_hash(new)
    return jsonify({"ok": True, "note": "已生效（重启后恢复为环境变量中的密码）"})


@app.errorhandler(404)
def e404(_):
    return render_template("share.html", error_page=("404", "链接不存在或已被删除")), 404


@app.errorhandler(410)
def e410(_):
    return render_template("share.html", error_page=("410", "该分享链接已过期")), 410


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
