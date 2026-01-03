from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, abort, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic"}
LIBRARY_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


@app.route("/")
def index() -> str:
    libraries = sorted(
        [p.name for p in DATA_DIR.iterdir() if p.is_dir()],
        key=str.casefold,
    )
    return render_template("index.html", libraries=libraries)


@app.post("/libraries")
def create_library():
    library_id = request.form.get("library_id", "").strip()
    if not LIBRARY_ID_PATTERN.match(library_id):
        return render_template(
            "index.html",
            libraries=_library_list(),
            error="IDは3〜32文字の英数字・ハイフン・アンダースコアで入力してください。",
        )

    library_path = DATA_DIR / library_id
    if library_path.exists():
        return render_template(
            "index.html",
            libraries=_library_list(),
            error="同じIDがすでに登録されています。",
        )

    library_path.mkdir(parents=True)
    return redirect(url_for("library_detail", library_id=library_id))


@app.get("/libraries/<library_id>")
def library_detail(library_id: str) -> str:
    library_path = DATA_DIR / library_id
    if not library_path.exists():
        abort(404)

    photos = sorted(
        [p.name for p in library_path.iterdir() if p.is_file()],
        reverse=True,
    )
    return render_template(
        "library.html",
        library_id=library_id,
        photos=photos,
    )


@app.post("/libraries/<library_id>/photos")
def upload_photo(library_id: str):
    library_path = DATA_DIR / library_id
    if not library_path.exists():
        abort(404)

    if "photo" not in request.files:
        return redirect(url_for("library_detail", library_id=library_id))

    file = request.files["photo"]
    if not file or not file.filename:
        return redirect(url_for("library_detail", library_id=library_id))

    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return render_template(
            "library.html",
            library_id=library_id,
            photos=_photo_list(library_id),
            error="対応形式は jpg / png / webp / heic です。",
        )

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stored_name = f"{timestamp}_{filename}"
    file.save(library_path / stored_name)

    return redirect(url_for("library_detail", library_id=library_id))


@app.route("/uploads/<library_id>/<path:filename>")
def uploaded_file(library_id: str, filename: str):
    library_path = DATA_DIR / library_id
    if not library_path.exists():
        abort(404)
    return send_from_directory(library_path, filename)


def _library_list() -> list[str]:
    return sorted(
        [p.name for p in DATA_DIR.iterdir() if p.is_dir()],
        key=str.casefold,
    )


def _photo_list(library_id: str) -> list[str]:
    library_path = DATA_DIR / library_id
    return sorted(
        [p.name for p in library_path.iterdir() if p.is_file()],
        reverse=True,
    )


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
