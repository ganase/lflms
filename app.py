from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from flask import (
    Flask,
    abort,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

try:
    from PIL import Image
except ImportError:  # pragma: no cover - handled by optional dependency
    Image = None

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp", "heic"}
LIBRARY_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")


@app.get("/login")
def login_form() -> str:
    return render_template("login.html")


@app.post("/login")
def login_submit():
    email = request.form.get("email", "").strip().lower()
    if not EMAIL_PATTERN.match(email):
        return render_template("login.html", error="有効なメールアドレスを入力してください。")

    session["email"] = email
    return redirect(url_for("index"))


@app.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("login_form"))


def _require_login():
    if "email" not in session:
        return redirect(url_for("login_form"))
    return None


@app.route("/")
def index() -> str:
    guard = _require_login()
    if guard:
        return guard

    libraries = sorted(
        [p.name for p in DATA_DIR.iterdir() if p.is_dir()],
        key=str.casefold,
    )
    return render_template("index.html", libraries=libraries, email=session.get("email"))


@app.post("/libraries")
def create_library():
    guard = _require_login()
    if guard:
        return guard

    library_id = request.form.get("library_id", "").strip()
    if not LIBRARY_ID_PATTERN.match(library_id):
        return render_template(
            "index.html",
            libraries=_library_list(),
            error="IDは3〜32文字の英数字・ハイフン・アンダースコアで入力してください。",
            email=session.get("email"),
        )

    library_path = DATA_DIR / library_id
    if library_path.exists():
        return render_template(
            "index.html",
            libraries=_library_list(),
            error="同じIDがすでに登録されています。",
            email=session.get("email"),
        )

    library_path.mkdir(parents=True)
    return redirect(url_for("library_detail", library_id=library_id))


@app.get("/libraries/<library_id>")
def library_detail(library_id: str) -> str:
    guard = _require_login()
    if guard:
        return guard

    library_path = DATA_DIR / library_id
    if not library_path.exists():
        abort(404)

    photos = sorted(
        [p.name for p in library_path.iterdir() if _is_photo(p)],
        reverse=True,
    )
    records = _load_records(library_id)
    records_by_name = {record["filename"]: record for record in records}
    return render_template(
        "library.html",
        library_id=library_id,
        photos=photos,
        records_by_name=records_by_name,
        email=session.get("email"),
    )


@app.post("/libraries/<library_id>/photos")
def upload_photo(library_id: str):
    guard = _require_login()
    if guard:
        return guard

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
            records_by_name=_records_map(library_id),
            error="対応形式は jpg / png / webp / heic です。",
            email=session.get("email"),
        )

    timestamp = datetime.now(timezone.utc)
    stored_name = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}_{filename}"
    stored_path = library_path / stored_name
    file.save(stored_path)

    capture_date = _extract_capture_date(stored_path)
    analysis = _analyze_image(stored_path)

    record = {
        "filename": stored_name,
        "uploaded_at": timestamp.isoformat(),
        "capture_date": capture_date,
        "analysis": analysis,
    }
    _append_record(library_id, record)

    return redirect(url_for("library_detail", library_id=library_id))


@app.route("/uploads/<library_id>/<path:filename>")
def uploaded_file(library_id: str, filename: str):
    guard = _require_login()
    if guard:
        return guard

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
        [p.name for p in library_path.iterdir() if _is_photo(p)],
        reverse=True,
    )


def _records_path(library_id: str) -> Path:
    return DATA_DIR / library_id / "records.json"


def _is_photo(path: Path) -> bool:
    if not path.is_file():
        return False
    ext = path.suffix.lstrip(".").lower()
    return ext in ALLOWED_EXTENSIONS


def _load_records(library_id: str) -> list[dict[str, Any]]:
    record_path = _records_path(library_id)
    if not record_path.exists():
        return []
    with record_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _append_record(library_id: str, record: dict[str, Any]) -> None:
    records = _load_records(library_id)
    records.insert(0, record)
    record_path = _records_path(library_id)
    with record_path.open("w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)


def _records_map(library_id: str) -> dict[str, dict[str, Any]]:
    return {record["filename"]: record for record in _load_records(library_id)}


def _extract_capture_date(path: Path) -> str | None:
    if Image is None:
        return None

    try:
        with Image.open(path) as image:
            exif = image.getexif()
            date_str = exif.get(36867) or exif.get(306)
    except Exception:
        return None

    if not date_str:
        return None

    try:
        parsed = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    except ValueError:
        return None

    return parsed.replace(tzinfo=timezone.utc).isoformat()


def _analyze_image(path: Path) -> dict[str, Any]:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"status": "skipped", "reason": "OPENAI_API_KEYが未設定です。"}

    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    api_base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    with path.open("rb") as handle:
        image_bytes = handle.read()
    image_b64 = _to_base64(image_bytes)

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "あなたは画像内の本の背表紙を解析し、書籍情報を抽出するアシスタントです。",
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "画像内の本の背表紙から、書名・著者名・出版社名を抽出し、"
                            "JSONで返してください。形式: [{\"title\": ..., \"author\": ..., \"publisher\": ...}, ...]"
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_b64}",
                        },
                    },
                ],
            },
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(
            f"{api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _parse_json_content(content)
        normalized = _normalize_analysis_data(parsed)
        return {"status": "ok", "data": normalized}
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


def _parse_json_content(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        list_match = re.search(r"\[.*\]", content, re.DOTALL)
        if list_match:
            try:
                return json.loads(list_match.group(0))
            except json.JSONDecodeError:
                pass
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return {"raw": content}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"raw": content}


def _normalize_analysis_data(parsed: Any) -> dict[str, Any]:
    if isinstance(parsed, list):
        return {"books": [_sanitize_book(item) for item in parsed if isinstance(item, dict)]}
    if isinstance(parsed, dict):
        if "books" in parsed and isinstance(parsed["books"], list):
            return {"books": [_sanitize_book(item) for item in parsed["books"] if isinstance(item, dict)]}
        if {"title", "author", "publisher"}.intersection(parsed.keys()):
            return {"books": [_sanitize_book(parsed)]}
        return parsed
    return {"raw": parsed}


def _sanitize_book(item: dict[str, Any]) -> dict[str, str]:
    return {
        "title": str(item.get("title") or "").strip(),
        "author": str(item.get("author") or "").strip(),
        "publisher": str(item.get("publisher") or "").strip(),
    }


def _to_base64(payload: bytes) -> str:
    import base64

    return base64.b64encode(payload).decode("utf-8")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    app.run(host="0.0.0.0", port=5000, debug=True)
