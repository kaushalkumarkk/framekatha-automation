import importlib
import os
import sys
from pathlib import Path


def connect():
    modules = os.environ.get("RESOLVE_SCRIPT_API_MODULES")
    if modules:
        sys.path.insert(0, modules)
    try:
        sdk = importlib.import_module("DaVinciResolveScript")
    except ImportError:
        raise RuntimeError(
            "Set RESOLVE_SCRIPT_API_MODULES to Resolve's Developer/Scripting/Modules"
        ) from None
    resolve = sdk.scriptapp("Resolve")
    if not resolve:
        raise RuntimeError("Start DaVinci Resolve Studio with local external scripting enabled")
    return resolve


def assemble(
    plan: dict,
    name: str,
    fps=24,
    lut=None,
    colour_preset=None,
    bgm=None,
    render_directory=None,
    render_preset=None,
    resolve=None,
):
    if not plan.get("clips") or plan.get("kind") != "rough_assembly":
        raise ValueError("A nonempty rough-assembly plan is required")
    if fps <= 0 or fps > 120:
        raise ValueError("Invalid timeline frame rate")
    for clip in plan["clips"]:
        if not Path(clip["media_path"]).is_file():
            raise ValueError("Media file is missing")
        if clip["start_seconds"] < 0 or clip["end_seconds"] <= clip["start_seconds"]:
            raise ValueError("Invalid source clip range")
    for asset in (lut, colour_preset, bgm):
        if asset and not Path(asset).is_file():
            raise ValueError("A selected LUT/grade/BGM asset is missing")
    resolve = resolve or connect()
    manager = resolve.GetProjectManager()
    project = manager.GetCurrentProject()
    if not project:
        raise RuntimeError("Open a project in Resolve Studio first")
    pool = project.GetMediaPool()
    timeline = pool.CreateEmptyTimeline(name)
    if not timeline or not project.SetCurrentTimeline(timeline):
        raise RuntimeError("Could not create the rough-cut timeline")
    if not timeline.SetSetting("timelineFrameRate", f"{fps:g}"):
        raise RuntimeError("Could not set timeline frame rate")
    timeline_start = timeline.GetStartFrame()
    for clip in plan["clips"]:
        media = pool.ImportMedia([clip["media_path"]])
        if not media:
            raise RuntimeError("Resolve could not import source media")
        source_fps = float(media[0].GetClipProperty("FPS") or fps)
        items = pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": media[0],
                    "startFrame": round(clip["start_seconds"] * source_fps),
                    "endFrame": round(clip["end_seconds"] * source_fps) - 1,
                    "recordFrame": timeline_start + round(clip["record_seconds"] * fps),
                }
            ]
        )
        if not items:
            raise RuntimeError("Resolve could not append a source clip")
        for item in items:
            if lut and not item.SetLUT(1, str(Path(lut).resolve())):
                raise RuntimeError("Resolve rejected the LUT; check node 1 and LUT installation")
        if colour_preset and not timeline.ApplyGradeFromDRX(
            str(Path(colour_preset).resolve()),
            0,
            items,
        ):
            raise RuntimeError("Resolve rejected the colour preset")
    if bgm:
        music = pool.ImportMedia([str(Path(bgm).resolve())])
        if not music:
            raise RuntimeError("Resolve could not import BGM")
        if timeline.GetTrackCount("audio") < 2 and not timeline.AddTrack("audio", "stereo"):
            raise RuntimeError("Could not add the BGM audio track")
        if not pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": music[0],
                    "mediaType": 2,
                    "trackIndex": 2,
                    "startFrame": 0,
                    "endFrame": round(plan["duration_seconds"] * fps) - 1,
                    "recordFrame": timeline_start,
                }
            ]
        ):
            raise RuntimeError(
                "Could not append BGM; ensure the track covers the assembly duration"
            )
    job_id = None
    if render_directory:
        target = Path(render_directory).resolve()
        target.mkdir(parents=True, exist_ok=True)
        if render_preset and not project.LoadRenderPreset(render_preset):
            raise RuntimeError("Resolve render preset not found")
        if not project.SetRenderSettings(
            {"TargetDir": str(target), "CustomName": name, "SelectAllFrames": True}
        ):
            raise RuntimeError("Could not configure render output")
        job_id = project.AddRenderJob()
        if not job_id:
            raise RuntimeError("Resolve could not queue the render")
    return {
        "timeline": name,
        "render_job_id": job_id,
        "render_started": False,
        "requires_editor_review": True,
    }
