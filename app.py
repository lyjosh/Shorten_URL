import os
import string
from datetime import datetime

from flask import Flask, request, jsonify, redirect, abort, render_template
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
import validators

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------- Model ----------
class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(16), unique=True, index=True, nullable=False)
    original_url = db.Column(db.Text, nullable=False)  # long URLs
    clicks = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

# ---------- Base62 ----------
ALPHABET = string.digits + string.ascii_letters

def base62_encode(num: int) -> str:
    if num == 0:
        return ALPHABET[0]
    base = len(ALPHABET)
    out = []
    while num > 0:
        num, rem = divmod(num, base)
        out.append(ALPHABET[rem])
    return ''.join(reversed(out))

# ---------- Bootstrap ----------
with app.app_context():
    db.create_all()

# ---------- Routes ----------
@app.route("/shorten", methods=["POST"])
def shorten_url():
    data = request.get_json(silent=True) or {}
    original_url = (data.get("url") or "").strip()

    if not original_url or not validators.url(original_url) or not original_url.startswith(("http://", "https://")):
        return jsonify({"error": "Provide a valid http(s) URL in JSON: {\"url\": \"...\"}"}), 400

    # Insert with a placeholder slug so we can get the auto-increment id
    link = Link(original_url=original_url, slug="")  # temporary empty string
    db.session.add(link)
    db.session.commit()  # link.id is now set

    # Compute slug from id (Base62) and update once
    slug = base62_encode(link.id)
    link.slug = slug
    db.session.commit()

    base_url = os.getenv("BASE_URL", "http://127.0.0.1:5023")
    return jsonify({"short_url": f"{base_url}/{slug}", "slug": slug})

@app.route("/<slug>", methods=["GET"])
def resolve(slug):
    link = Link.query.filter_by(slug=slug).first()
    if not link:
        abort(404)
    link.clicks += 1
    db.session.commit()
    return redirect(link.original_url, code=302)

@app.route("/stats/<slug>", methods=["GET"])
def stats(slug):
    link = Link.query.filter_by(slug=slug).first()
    if not link:
        abort(404)
    return jsonify({
        "slug": link.slug,
        "original_url": link.original_url,
        "clicks": link.clicks,
        "created_at": link.created_at.isoformat() + "Z"
    })

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port = 5023)