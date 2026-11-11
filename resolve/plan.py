from pathlib import Path

from rapidfuzz.fuzz import WRatio


def build_plan(script: dict, transcripts: list[dict], threshold: float = 65) -> dict:
    document = script.get("output", script)
    clips, unmatched, used = [], [], set()
    cursor = 0.0
    for shot in document.get("shooting_script", []):
        dialogue = str(shot.get("dialogue", "")).strip()
        if not dialogue:
            unmatched.append(
                {
                    "scene_id": shot.get("scene_id"),
                    "reason": "Visual-only shot needs manual media selection",
                }
            )
            continue
        candidates = []
        for transcript in transcripts:
            for index, segment in enumerate(transcript.get("segments", [])):
                identity = (transcript["media_path"], index)
                if identity in used:
                    continue
                score = WRatio(dialogue.casefold(), segment["text"].casefold())
                if score >= threshold:
                    candidates.append((score, identity, segment))
        if not candidates:
            unmatched.append({"scene_id": shot.get("scene_id"), "reason": "No transcript match"})
            continue
        score, identity, segment = max(candidates, key=lambda row: row[0])
        start, end = float(segment["start"]), float(segment["end"])
        end = min(end, start + float(shot.get("duration_seconds", end - start)))
        if start < 0 or end <= start:
            unmatched.append(
                {"scene_id": shot.get("scene_id"), "reason": "Invalid transcript range"}
            )
            continue
        used.add(identity)
        clips.append(
            {
                "media_path": str(Path(identity[0]).resolve()),
                "scene_id": shot["scene_id"],
                "start_seconds": start,
                "end_seconds": end,
                "record_seconds": cursor,
                "match_score": score,
            }
        )
        cursor += end - start
    return {
        "version": 1,
        "kind": "rough_assembly",
        "clips": clips,
        "duration_seconds": cursor,
        "unmatched_shots": unmatched,
        "requires_editor_review": True,
    }
