import json
import os
import re
import shlex
import subprocess
import tempfile
import urllib.request
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header
from sqlalchemy import text
from uuid import UUID

from app.db import engine
from app.core.deps import require_admin
from app.schemas.voice import VoiceSceneDraft

router = APIRouter(
    prefix="/admin/scenes",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

def _pick_lang(lang: Optional[str]) -> str:
    if not lang:
        return "de"
    lang = lang.lower()
    if lang.startswith("de"):
        return "de"
    if lang.startswith("en"):
        return "en"
    return "de"

def _normalize_text(text: str) -> str:
    text = text.lower()
    return (
        text.replace("ä", "ae")
            .replace("ö", "oe")
            .replace("ü", "ue")
            .replace("ß", "ss")
            .replace("\u00e4", "ae")
            .replace("\u00f6", "oe")
            .replace("\u00fc", "ue")
            .replace("\u00df", "ss")
    )


_FOOTBALL_TERMS = None


def _find_i18n_dir() -> Optional[str]:
    env_dir = (os.getenv("MV_I18N_DIR") or "").strip()
    candidates = []
    if env_dir:
        candidates.append(env_dir)
    candidates.append(os.path.join(os.getcwd(), "backend", "resources", "i18n"))
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        candidates.append(os.path.join(cur, "backend", "resources", "i18n"))
        cur = os.path.dirname(cur)
    for candidate in candidates:
        if candidate and os.path.isdir(candidate):
            return candidate
    return None


def _load_json(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _term_to_pattern(term: str) -> str:
    def _space_hyphen(value: str) -> str:
        pattern = re.escape(value.strip())
        pattern = pattern.replace("\\ ", r"[\\s\\-]*")
        pattern = pattern.replace("\\-", r"[\\s\\-]*")
        return pattern

    orig = _space_hyphen(term)
    norm = _space_hyphen(_normalize_text(term))
    if norm != orig:
        return r"\b(?:" + orig + "|" + norm + r")\b"
    return r"\b" + orig + r"\b"


def _load_football_terms():
    global _FOOTBALL_TERMS
    if _FOOTBALL_TERMS is not None:
        return _FOOTBALL_TERMS
    base = _find_i18n_dir()
    if not base:
        _FOOTBALL_TERMS = []
        return _FOOTBALL_TERMS
    de_path = os.path.join(base, "football_terms.de.json")
    en_path = os.path.join(base, "football_terms.en.json")
    de_terms = _load_json(de_path).get("football", {})
    en_terms = _load_json(en_path).get("football", {})
    pairs = []
    for key, de_term in de_terms.items():
        en_term = en_terms.get(key)
        if not de_term or not en_term:
            continue
        pairs.append((_term_to_pattern(de_term), de_term, en_term))
    pairs.sort(key=lambda item: len(item[1]), reverse=True)
    _FOOTBALL_TERMS = pairs
    return _FOOTBALL_TERMS


def _apply_glossary(text: str) -> str:
    if not text:
        return text
    for pattern, _de_term, en_term in _load_football_terms():
        text = re.sub(pattern, en_term, text, flags=re.IGNORECASE)
    return text


def _fix_german_terms(text: str) -> str:
    if not text:
        return text
    for pattern, de_term, _en_term in _load_football_terms():
        text = re.sub(pattern, de_term, text, flags=re.IGNORECASE)
    return text


def _post_translate_fix(text: str) -> str:
    if not text:
        return text
    replacements = [
        (r"\bred\s*map\b", "red card"),
        (r"\bnudbremser\b", "DOGSO"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text


def _translate_text(text: str, source: str = "de", target: str = "en") -> Optional[str]:
    if source == "de":
        text = _apply_glossary(text)
    url = (os.getenv("MV_TRANSLATE_URL") or "").strip()
    if not url:
        return None
    payload = json.dumps({
        "q": text,
        "source": source,
        "target": target,
        "format": "text",
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
        data = json.loads(body)
        translated = (data or {}).get("translatedText")
        return _post_translate_fix(translated or "")
    except Exception:
        return None

def _extract_scene_type(text: str):
    text = _normalize_text(text)
    matches = [
        ("PENALTY_OVERTURNED", ["elfmeter zurueck", "penalty overturned"]),
        ("PENALTY_REVIEW", ["elfmeter-check", "penalty review", "penalty check"]),
        ("PENALTY", ["elfmeter", "penalty"]),
        ("SECOND_YELLOW", ["zweite gelbe", "gelb-rot", "second yellow"]),
        ("RED_CARD", ["rote karte", "rotekarte", "red card", "rot"]),
        ("YELLOW_CARD", ["gelbe karte", "gelbekarte", "yellow card", "gelb"]),
        ("OFFSIDE_GOAL", ["tor im abseits", "offside goal"]),
        ("GOAL_DISALLOWED", ["tor aberkannt", "aberkanntes tor", "goal disallowed"]),
        ("OFFSIDE", ["abseits", "offside"]),
        ("VAR_DECISION", ["var-entscheidung", "var decision"]),
        ("VAR_REVIEW", ["var-check", "var check", "var review", "var pruefung", "var pruefungen"]),
        ("HANDBALL", ["handspiel", "handball"]),
        ("DENIED_GOALSCORING_OPPORTUNITY", ["notbremse", "dogso"]),
        ("INDIRECT_FREE_KICK", ["indirekter freistoss", "indirect free kick"]),
        ("FREE_KICK", ["freistoss", "free kick"]),
        ("DROP_BALL", ["schiedsrichterball", "drop ball"]),
        ("FOUL", ["foul", "faul"]),
        ("SUBSTITUTION", ["wechsel", "substitution"]),
        ("INJURY_STOPPAGE", ["verletzung", "injury"]),
        ("TIME_WASTING", ["zeitspiel", "time wasting"]),
        ("DISSENT", ["unsportlich", "meckern", "dissent"]),
        ("CORNER", ["ecke", "corner"]),
        ("GOAL_KICK", ["abstoss", "goal kick"]),
        ("THROW_IN", ["einwurf", "throw in", "throw-in"]),
        ("GOAL", ["tor", "goal"]),
    ]
    for scene_type, keywords in matches:
        if any(k in text for k in keywords):
            return scene_type
    return None

def _extract_minute_stoppage(text: str):
    minute = None
    stoppage = None
    plus_match = re.search(r"(\d{1,3})\s*\+\s*(\d{1,2})", text)
    if plus_match:
        minute = int(plus_match.group(1))
        stoppage = int(plus_match.group(2))
        return minute, stoppage

    stoppage_match = re.search(r"(nachspielzeit|zusatzzeit|stoppage)\s*(\d{1,2})", text)
    if stoppage_match:
        stoppage = int(stoppage_match.group(2))

    minute_match = re.search(r"(?:minute|min)\s*[:\.]?\s*(\d{1,3})", text)
    if minute_match:
        minute = int(minute_match.group(1))
    else:
        minute_match = re.search(r"(\d{1,3})\s*[\.,]?\s*(?:minute|min)\b", text)
        if minute_match:
            minute = int(minute_match.group(1))
        else:
            minute_match = re.search(r"(\d{1,3})\.?\s*(?:min)\.\b", text)
            if minute_match:
                minute = int(minute_match.group(1))
            else:
                loose = re.search(r"\b(\d{1,3})\b", text)
                if loose:
                    minute = int(loose.group(1))

    if minute is not None and (minute < 0 or minute > 130):
        minute = None
    if stoppage is not None and (stoppage < 0 or stoppage > 30):
        stoppage = None
    return minute, stoppage

async def _transcribe_audio(audio: UploadFile, lang: str) -> str:
    cmd_template = (os.getenv("MV_ASR_CMD") or "").strip()
    if not cmd_template:
        raise HTTPException(
            status_code=501,
            detail="ASR not configured. Provide transcript or set MV_ASR_CMD.",
        )

    suffix = os.path.splitext(audio.filename or "")[1] or ".webm"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await audio.read())
        tmp_path = tmp.name
    out_base = None
    out_txt = None

    try:
        if "{out}" in cmd_template:
            fd, out_base = tempfile.mkstemp(prefix="mv_asr_")
            os.close(fd)
            try:
                os.remove(out_base)
            except OSError:
                pass
            out_txt = out_base + ".txt"
        cmd = cmd_template.format(audio=tmp_path, lang=lang, out=out_base or "")
        parts = shlex.split(cmd)
        result = subprocess.run(parts, capture_output=True, text=True)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            raise HTTPException(status_code=502, detail=f"ASR failed: {detail or 'unknown error'}")
        if out_txt and os.path.exists(out_txt):
            with open(out_txt, "r", encoding="utf-8") as handle:
                transcript = handle.read().strip()
        else:
            transcript = (result.stdout or "").strip()
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        if out_txt:
            try:
                os.remove(out_txt)
            except OSError:
                pass

    if not transcript:
        raise HTTPException(status_code=502, detail="ASR returned empty transcript.")
    return transcript

@router.post("/voice-draft", response_model=VoiceSceneDraft)
async def voice_draft(
    transcript: Optional[str] = Form(default=None),
    lang: Optional[str] = Form(default=None),
    audio: Optional[UploadFile] = File(default=None),
    accept_language: Optional[str] = Header(default=None, alias="Accept-Language"),
):
    lang = _pick_lang(lang or accept_language)
    transcript = (transcript or "").strip()
    if not transcript:
        if not audio:
            raise HTTPException(status_code=400, detail="audio or transcript required")
        transcript = (await _transcribe_audio(audio, lang)).strip()

    normalized = _normalize_text(transcript)
    minute, stoppage = _extract_minute_stoppage(normalized)
    scene_type = _extract_scene_type(normalized)
    notes = None
    if minute is None:
        notes = "Minute not detected; please verify."

    description_de = _fix_german_terms(transcript)
    description_en = transcript
    if lang == "de":
        translated = _translate_text(transcript, source="de", target="en")
        if translated:
            description_en = translated

    return VoiceSceneDraft(
        transcript=transcript,
        minute=minute,
        stoppage_time=stoppage,
        scene_type=scene_type,
        description_de=description_de,
        description_en=description_en,
        notes=notes,
    )

@router.post("/{scene_id}/release")
def release_scene(scene_id: UUID):
    sql = text("""
        update referee_ratings.scenes
        set is_released = true,
            release_time = now()
        where scene_id = cast(:scene_id as uuid)
        returning scene_id::text as scene_id, is_released, release_time
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")
    return dict(row)

@router.post("/{scene_id}/unrelease")
def unrelease_scene(scene_id: UUID):
    sql = text("""
        update referee_ratings.scenes
        set is_released = false,
            release_time = null
        where scene_id = cast(:scene_id as uuid)
        returning scene_id::text as scene_id, is_released, release_time
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")
    return dict(row)

@router.post("/{scene_id}/delete", status_code=204)
def delete_scene(scene_id: UUID):
    sql = text("""
        delete from referee_ratings.scenes
        where scene_id = cast(:scene_id as uuid)
        returning scene_id::text as scene_id
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")

@router.post("/{scene_id}/lock")
def lock_scene(scene_id: UUID):
    sql = text("""
        update referee_ratings.scenes
        set is_locked = true
        where scene_id = cast(:scene_id as uuid)
        returning scene_id::text as scene_id, is_locked
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")
    return dict(row)

@router.post("/{scene_id}/unlock")
def unlock_scene(scene_id: UUID):
    sql = text("""
        update referee_ratings.scenes
        set is_locked = false
        where scene_id = cast(:scene_id as uuid)
        returning scene_id::text as scene_id, is_locked
    """)
    with engine.begin() as conn:
        row = conn.execute(sql, {"scene_id": str(scene_id)}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Scene not found")
    return dict(row)
















