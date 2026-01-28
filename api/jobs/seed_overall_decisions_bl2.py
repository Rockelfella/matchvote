import argparse
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from app.db import engine

IMPORT_RELEASE_IMMEDIATELY = os.getenv("IMPORT_RELEASE_IMMEDIATELY", "true").lower() in ("1", "true", "yes", "y")
IMPORT_LOG = os.getenv("IMPORT_LOG")
IMPORT_CREATED_BY = os.getenv("IMPORT_CREATED_BY")

DESCRIPTION_DE = "Gesamtwertung Entscheidungen"
DESCRIPTION_EN = "Overall Decisions"
LEGACY_MARKER = "auto_overall_decisions"
SCENE_TYPE = "OVERALL_DECISIONS"
SCENE_MINUTE = 90
LEAGUE = "BL2"


def log(message):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"{ts} {message}"
    print(line)
    if IMPORT_LOG:
        with open(IMPORT_LOG, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def column_exists(conn, schema, table, column):
    row = conn.execute(text("""
        select 1
        from information_schema.columns
        where table_schema = :schema
          and table_name = :table
          and column_name = :column
        limit 1
    """), {"schema": schema, "table": table, "column": column}).first()
    return bool(row)


def scene_exists(conn, match_id, use_legacy):
    if use_legacy:
        sql = text("""
            select 1
            from referee_ratings.scenes
            where match_id = cast(:match_id as uuid)
              and scene_type = :scene_type
              and minute = :minute
              and description = :marker
            limit 1
        """)
        params = {"match_id": str(match_id), "scene_type": SCENE_TYPE, "minute": SCENE_MINUTE, "marker": LEGACY_MARKER}
    else:
        sql = text("""
            select 1
            from referee_ratings.scenes
            where match_id = cast(:match_id as uuid)
              and scene_type = :scene_type
              and minute = :minute
              and description_de = :description_de
              and description_en = :description_en
            limit 1
        """)
        params = {
            "match_id": str(match_id),
            "scene_type": SCENE_TYPE,
            "minute": SCENE_MINUTE,
            "description_de": DESCRIPTION_DE,
            "description_en": DESCRIPTION_EN,
        }
    row = conn.execute(sql, params).first()
    return row is not None


def insert_scene(conn, match_id, use_legacy):
    if use_legacy:
        sql = text("""
            insert into referee_ratings.scenes
              (match_id, minute, stoppage_time, scene_type, description, description_de, description_en, is_released, release_time, created_by)
            values
              (:match_id, :minute, null, :scene_type, :description, :description_de, :description_en, :is_released, :release_time, :created_by)
        """)
    else:
        sql = text("""
            insert into referee_ratings.scenes
              (match_id, minute, stoppage_time, scene_type, description_de, description_en, is_released, release_time, created_by)
            values
              (:match_id, :minute, null, :scene_type, :description_de, :description_en, :is_released, :release_time, :created_by)
        """)
    params = {
        "match_id": str(match_id),
        "minute": SCENE_MINUTE,
        "scene_type": SCENE_TYPE,
        "description": LEGACY_MARKER,
        "description_de": DESCRIPTION_DE,
        "description_en": DESCRIPTION_EN,
        "is_released": IMPORT_RELEASE_IMMEDIATELY,
        "release_time": datetime.now(timezone.utc) if IMPORT_RELEASE_IMMEDIATELY else None,
        "created_by": IMPORT_CREATED_BY,
    }
    conn.execute(sql, params)


def main():
    parser = argparse.ArgumentParser(description="Seed OVERALL_DECISIONS scenes at minute 90 for BL2 matches")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    inserted = 0
    skipped = 0
    total = 0

    with engine.begin() as conn:
        use_legacy = column_exists(conn, "referee_ratings", "scenes", "description")
        rows = conn.execute(text("""
            select match_id
            from referee_ratings.matches
            where league = :league
        """), {"league": LEAGUE}).mappings().all()
        for row in rows:
            total += 1
            match_id = row["match_id"]
            if scene_exists(conn, match_id, use_legacy):
                skipped += 1
                continue
            if args.dry_run:
                log(f"[dry-run] Would insert {SCENE_TYPE} scene match_id={match_id}")
                inserted += 1
                continue
            insert_scene(conn, match_id, use_legacy)
            inserted += 1

    log(f"Done matches={total} inserted={inserted} skipped={skipped} dry_run={args.dry_run}")


if __name__ == "__main__":
    main()
