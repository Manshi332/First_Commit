# evidence.py
"""AI-assisted resolution-evidence check.

Tier 1: a local Ollama vision model (default `llava`) judges the photo.
Tier 2: transparent heuristics - image sanity, EXIF GPS distance to the ticket,
        and keywords in filename / officer notes.  Every check reports its
        basis, so the UI never over-claims what was verified.
"""
import base64
import hashlib
import io
import json
import math
import os
import re
import urllib.request

from PIL import Image, ImageStat

VISION_MODEL = os.getenv("CIVIC_VISION_MODEL", "llava")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
USE_VISION = os.getenv("CIVIC_USE_VISION", "1") == "1"
MAX_KM = 1.5

SUBJECT_WORDS = {
    "Electrical": ["light", "lamp", "pole", "cable", "wire", "electric", "transformer", "bulb"],
    "Water": ["pipe", "water", "leak", "valve", "hydrant", "pump", "tap"],
    "Roads": ["road", "pothole", "asphalt", "footpath", "pavement", "slab", "patch"],
    "Sanitation": ["garbage", "waste", "bin", "kachra", "drain", "naali", "clean", "sweep"],
}
RESOLVED_RE = re.compile(r"\b(fixed|repaired|replaced|restored|cleared|cleaned|patched|"
                         r"resurfaced|sealed|removed|completed|done)\b", re.I)


def _dept_key(category):
    c = category.lower()
    return next((k for k, w in (("Electrical", "electr"), ("Water", "water"),
                                ("Roads", "road"), ("Sanitation", "sanit")) if w in c), "Roads")


def _dms(v, ref):
    d = float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
    return -d if ref in ("S", "W") else d


def _exif_gps(img):
    try:
        gps = img.getexif().get_ifd(0x8825)
        if gps and 2 in gps and 4 in gps:
            return _dms(gps[2], gps.get(1, "N")), _dms(gps[4], gps.get(3, "E"))
    except Exception:
        pass
    return None


def _km(a, b):
    r = 6371.0
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dp, dl = p2 - p1, math.radians(b[1] - a[1])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _vision(image_bytes, ticket):
    """Ask a local vision model; returns dict or None if unavailable."""
    if not USE_VISION:
        return None
    prompt = (f"A municipal crew says they fixed this issue: '{ticket['title']}' "
              f"(department: {ticket['category']}). Look at the photo and reply ONLY with JSON: "
              '{"shows_expected_infrastructure": true/false, "issue_appears_resolved": true/false, '
              '"description": "one short sentence"}')
    body = json.dumps({"model": VISION_MODEL, "stream": False, "format": "json",
                       "messages": [{"role": "user", "content": prompt,
                                     "images": [base64.b64encode(image_bytes).decode()]}]}).encode()
    try:
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/chat", body,
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            content = json.loads(r.read())["message"]["content"]
        data = json.loads(content)
        return {"subject": bool(data.get("shows_expected_infrastructure")),
                "resolved": bool(data.get("issue_appears_resolved")),
                "description": str(data.get("description", ""))[:160]}
    except Exception:
        return None


def verify_resolution(image_bytes, filename, ticket, notes="", vision_cache=None) -> dict:
    checks, dept = [], _dept_key(ticket["category"])
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.load()
    except Exception:
        return {"mode": "none", "verdict": "NEEDS REVIEW", "checks": [
            {"label": "Valid photo", "status": "fail", "detail": "File could not be read as an image."}]}

    w, h = img.size
    stddev = sum(ImageStat.Stat(img.convert("L")).stddev)
    if min(w, h) < 200:
        checks.append({"label": "Photo quality", "status": "fail", "detail": f"Too small ({w}×{h}px)."})
    elif stddev < 3:
        checks.append({"label": "Photo quality", "status": "fail", "detail": "Image looks blank or uniform."})
    else:
        checks.append({"label": "Photo quality", "status": "pass", "detail": f"{w}×{h}px, usable detail."})

    key = hashlib.sha256(image_bytes).hexdigest() + ticket["ticket_id"]
    vis = None
    if vision_cache is not None and key in vision_cache:
        vis = vision_cache[key]
    else:
        vis = _vision(image_bytes, ticket)
        if vision_cache is not None:
            vision_cache[key] = vis
    mode = "vision" if vis else "heuristic"

    text = f"{filename} {notes}".lower()
    kw = next((k for k in SUBJECT_WORDS[dept] if k in text), None)
    if vis:
        checks.append({"label": f"Image appears to show {dept.lower()} infrastructure",
                       "status": "pass" if vis["subject"] else "fail",
                       "detail": f"Vision model ({VISION_MODEL}): {vis['description']}"})
    elif kw:
        checks.append({"label": f"Image appears to show {dept.lower()} infrastructure", "status": "pass",
                       "detail": f"Filename/notes mention “{kw}” (no vision model available)."})
    else:
        checks.append({"label": f"Image appears to show {dept.lower()} infrastructure", "status": "warn",
                       "detail": "Cannot confirm the subject automatically — add a caption or start Ollama with a vision model."})

    gps = _exif_gps(img)
    if gps:
        d = _km(gps, (ticket["lat"], ticket["lon"]))
        checks.append({"label": "Location approximately matches",
                       "status": "pass" if d <= MAX_KM else "fail",
                       "detail": f"Photo GPS is {d:.1f} km from the reported location."})
    else:
        checks.append({"label": "Location approximately matches", "status": "warn",
                       "detail": "Photo has no GPS metadata, so location could not be verified."})

    if vis:
        checks.append({"label": "Issue appears resolved", "status": "pass" if vis["resolved"] else "fail",
                       "detail": "Vision model judged the issue " + ("resolved." if vis["resolved"] else "still present.")})
    elif RESOLVED_RE.search(notes or ""):
        checks.append({"label": "Issue appears resolved", "status": "pass",
                       "detail": "Officer notes describe the completed fix (not visually verified)."})
    else:
        checks.append({"label": "Issue appears resolved", "status": "warn",
                       "detail": "No description of the fix — add work notes."})

    fails = any(c["status"] == "fail" for c in checks)
    warns = any(c["status"] == "warn" for c in checks)
    verdict = "NEEDS REVIEW" if fails else "VERIFIED (with warnings)" if warns else "VERIFIED"
    return {"mode": mode, "verdict": verdict, "checks": checks}