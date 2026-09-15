"""Voice-to-text for the complaint desk.
Uses SpeechRecognition (Google Web Speech, free, needs internet).
No API key, no PyAudio needed for file/bytes transcription.
"""
import io
import tempfile
import os

LANG_MAP = {
    "Hindi / Hinglish": "hi-IN",
    "English": "en-IN",
    "Auto (Hindi+English)": "hi-IN",
}

def transcribe_bytes(data: bytes, language="hi-IN") -> str:
    """Transcribe raw audio bytes (wav from st.audio_input). Raises RuntimeError with friendly msg."""
    try:
        import speech_recognition as sr
    except ImportError:
        raise RuntimeError("Voice library not installed. Run: pip install SpeechRecognition")
    if not data:
        raise RuntimeError("Empty recording. Please record again.")
    # st.audio_input gives wav bytes; write to temp file for AudioFile
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        r = sr.Recognizer()
        with sr.AudioFile(path) as src:
            audio = r.record(src)
        # try requested language, fall back to en-IN
        for lang in [language, "en-IN", "hi-IN"]:
            try:
                return r.recognize_google(audio, language=lang)
            except sr.UnknownValueError:
                continue
        raise RuntimeError("Could not understand the audio. Please speak clearly or type instead.")
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(f"Transcription failed ({e}). Check internet and try again.")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

def transcribe_upload(file_bytes: bytes, filename: str, language="hi-IN") -> str:
    """Transcribe an uploaded audio file (wav recommended; mp3 needs ffmpeg)."""
    name = (filename or "").lower()
    if name.endswith(".wav") or not name:
        return transcribe_bytes(file_bytes, language)
    # try wav path anyway; mp3/ogg need ffmpeg via pydub
    try:
        from pydub import AudioSegment
        with tempfile.NamedTemporaryFile(suffix="_in", delete=False) as f:
            f.write(file_bytes)
            in_path = f.name
        out_path = in_path + ".wav"
        AudioSegment.from_file(in_path).export(out_path, format="wav")
        with open(out_path, "rb") as f:
            data = f.read()
        for p in (in_path, out_path):
            try:
                os.remove(p)
            except OSError:
                pass
        return transcribe_bytes(data, language)
    except ImportError:
        raise RuntimeError("MP3 needs ffmpeg + pydub. Please upload a WAV file instead.")
    except Exception as e:
        raise RuntimeError(f"Could not convert audio ({e}). Upload WAV instead.")
