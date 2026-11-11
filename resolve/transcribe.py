from functools import lru_cache


@lru_cache(maxsize=1)
def whisper_model(model_name):
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "Install framekatha-resolve[transcription] on the editing machine"
        ) from None
    # CPU/int8 keeps local development usable; Studio workstation can configure a GPU separately.
    return WhisperModel(model_name, device="cpu", compute_type="int8")


def transcribe(path, model_name="small", language=None):
    model = whisper_model(model_name)
    segments, info = model.transcribe(str(path), language=language, vad_filter=True)
    return {
        "media_path": str(path.resolve()),
        "language": info.language,
        "segments": [
            {"start": segment.start, "end": segment.end, "text": segment.text.strip()}
            for segment in segments
        ],
    }
