import math
import unicodedata
from pathlib import Path

from rapidfuzz.fuzz import ratio


def normalized(text: str) -> str:
    # Keep vowel signs and combining marks in Hindi, Bengali and other scripts.
    cleaned = "".join(
        c if unicodedata.category(c)[0] in {"L", "N", "M"} else " " for c in text.casefold()
    )
    return " ".join(cleaned.split())


def build_plan(script: dict, transcripts: list[dict], threshold: float = 65) -> dict:
    if not math.isfinite(threshold) or not 0 <= threshold <= 100:
        raise ValueError("Match threshold must be between 0 and 100")
    document = script.get("output", script)
    clips, unmatched, used, warnings = [], [], {}, []
    cursor = 0.0
    for shot in document.get("shooting_script", []):
        dialogue = normalized(str(shot.get("dialogue", "")))
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
            media = str(Path(transcript["media_path"]).resolve())
            segments = transcript.get("segments", [])
            for index in range(len(segments)):
                words, start, previous_end = [], None, None
                # A dialogue line may span several consecutive transcription segments.
                for segment in segments[index : index + 8]:
                    begin, end = float(segment["start"]), float(segment["end"])
                    if not (math.isfinite(begin) and math.isfinite(end) and 0 <= begin < end):
                        break
                    if previous_end is not None and not 0 <= begin - previous_end <= 1.5:
                        break
                    start = begin if start is None else start
                    if any(start < right and end > left for left, right in used.get(media, [])):
                        break
                    words.append(str(segment["text"]))
                    previous_end = end
                    text = " ".join(words)
                    score = ratio(dialogue, normalized(text))
                    if score >= threshold:
                        candidates.append((score, media, start, end, text))
        if not candidates:
            unmatched.append({"scene_id": shot.get("scene_id"), "reason": "No transcript match"})
            continue
        score, media, start, end, text = max(candidates, key=lambda row: row[0])
        used.setdefault(media, []).append((start, end))
        # Preserve the entire spoken line; trimming to the target runtime can cut words.
        if end - start > float(shot.get("duration_seconds", end - start)):
            warnings.append(
                {
                    "scene_id": shot.get("scene_id"),
                    "reason": "Dialogue exceeds planned shot duration; review pacing",
                }
            )
        clips.append(
            {
                "media_path": media,
                "scene_id": shot["scene_id"],
                "shot_number": shot.get("shot_number"),
                "start_seconds": start,
                "end_seconds": end,
                "record_seconds": cursor,
                "match_score": score,
                "matched_text": text,
            }
        )
        cursor += end - start
    return {
        "version": 1,
        "kind": "rough_assembly",
        "clips": clips,
        "duration_seconds": cursor,
        "unmatched_shots": unmatched,
        "warnings": warnings,
        "requires_editor_review": True,
    }
