from __future__ import annotations

import io
import os
import re
import subprocess
import tarfile
import tempfile
import threading
import urllib.request
import wave
from pathlib import Path
from typing import Any

import numpy as np
from faster_whisper import WhisperModel

from english_tech.config import (
    PIPER_ARCHIVE_PATH,
    PIPER_ARCHIVE_URL,
    PIPER_BINARY_PATH,
    PIPER_BIN_DIR,
    PIPER_ROOT,
    PIPER_VOICE_CONFIG_PATH,
    PIPER_VOICE_CONFIG_URL,
    PIPER_VOICE_MODEL_PATH,
    PIPER_VOICE_MODEL_URL,
    STT_COMPUTE_TYPE,
    STT_DEVICE,
    STT_LANGUAGE,
    STT_MODEL_NAME,
    STREAM_TTS_SEGMENT_MAX_CHARS,
    TTS_RATE,
)


class SpeechService:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stt_model: WhisperModel | None = None
        self._stt_device = STT_DEVICE
        self._stt_compute_type = STT_COMPUTE_TYPE
        self._piper_ready = False

    def transcribe_wav(self, audio_bytes: bytes, *, language: str | None = None) -> dict[str, Any]:
        audio, duration_seconds = self._decode_wav(audio_bytes)
        return self._transcribe_audio(audio, duration_seconds=duration_seconds, language=language)

    def transcribe_pcm16(self, pcm_bytes: bytes, *, sample_rate: int = 16000, language: str | None = None) -> dict[str, Any]:
        if not pcm_bytes:
            raise ValueError("Audio stream is empty")
        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        duration_seconds = len(audio) / float(sample_rate or 16000)
        if sample_rate != 16000:
            audio = self._resample(audio, sample_rate, 16000)
        return self._transcribe_audio(audio.astype(np.float32), duration_seconds=duration_seconds, language=language)

    def iter_audio_chunks(self, audio_bytes: bytes, *, chunk_size: int = 16384):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        for index in range(0, len(audio_bytes), chunk_size):
            yield audio_bytes[index:index + chunk_size]

    def split_tts_segments(self, text: str, *, max_chars: int = STREAM_TTS_SEGMENT_MAX_CHARS) -> list[str]:
        clean_text = " ".join(text.split()).strip()
        if not clean_text:
            return []
        if len(clean_text) <= max_chars:
            return [clean_text]

        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\\s+", clean_text) if part.strip()]
        segments: list[str] = []
        for sentence in sentences:
            if len(sentence) <= max_chars:
                segments.append(sentence)
                continue
            clauses = [part.strip() for part in re.split(r"(?<=[,;:])\\s+", sentence) if part.strip()]
            current = ""
            for clause in clauses:
                candidate = clause if not current else f"{current} {clause}"
                if len(candidate) <= max_chars:
                    current = candidate
                    continue
                if current:
                    segments.append(current)
                if len(clause) <= max_chars:
                    current = clause
                    continue
                words = clause.split()
                current = ""
                for word in words:
                    candidate = word if not current else f"{current} {word}"
                    if len(candidate) <= max_chars:
                        current = candidate
                    else:
                        if current:
                            segments.append(current)
                        current = word
                if current:
                    segments.append(current)
                    current = ""
            if current:
                segments.append(current)
        return segments or [clean_text]

    def _transcribe_audio(self, audio: np.ndarray, *, duration_seconds: float, language: str | None = None) -> dict[str, Any]:
        model = self._get_model()
        try:
            raw_segments, info = model.transcribe(
                audio,
                language=language or STT_LANGUAGE,
                beam_size=1,
                vad_filter=True,
                word_timestamps=True,
            )
            segments = list(raw_segments)
        except Exception:
            if self._stt_device == "cpu":
                raise
            model = self._switch_to_cpu_model()
            raw_segments, info = model.transcribe(
                audio,
                language=language or STT_LANGUAGE,
                beam_size=1,
                vad_filter=True,
                word_timestamps=True,
            )
            segments = list(raw_segments)

        transcript_parts: list[str] = []
        words: list[dict[str, Any]] = []
        for segment in segments:
            if segment.text:
                transcript_parts.append(segment.text.strip())
            for word in segment.words or []:
                words.append(
                    {
                        "word": word.word.strip(),
                        "start": word.start,
                        "end": word.end,
                        "probability": word.probability,
                    }
                )

        transcript = " ".join(part for part in transcript_parts if part).strip()
        return {
            "text": transcript,
            "language": getattr(info, "language", language or STT_LANGUAGE),
            "duration_seconds": round(duration_seconds, 3),
            "words": words,
            "provider": "faster-whisper",
            "model": STT_MODEL_NAME,
            "device": self._stt_device,
        }

    async def synthesize_speech(
        self,
        text: str,
        *,
        voice: str | None = None,
        rate: str | None = None,
    ) -> bytes:
        del voice

        clean_text = " ".join(text.split()).strip()
        if not clean_text:
            raise ValueError("Text cannot be empty")

        self._ensure_piper_assets()
        length_scale = self._rate_to_length_scale(rate or TTS_RATE)

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as output_handle:
            output_path = Path(output_handle.name)

        command = [
            str(PIPER_BINARY_PATH),
            "--model",
            str(PIPER_VOICE_MODEL_PATH),
            "--config",
            str(PIPER_VOICE_CONFIG_PATH),
            "--output_file",
            str(output_path),
            "--length_scale",
            f"{length_scale:.3f}",
        ]
        env = os.environ.copy()
        ld_paths = [str(PIPER_BIN_DIR)]
        existing_ld = env.get("LD_LIBRARY_PATH")
        if existing_ld:
            ld_paths.append(existing_ld)
        env["LD_LIBRARY_PATH"] = ":".join(ld_paths)

        try:
            completed = subprocess.run(
                command,
                input=clean_text.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                env=env,
                cwd=str(PIPER_BIN_DIR),
            )
            if completed.returncode != 0:
                stderr = completed.stderr.decode("utf-8", errors="ignore").strip()
                raise RuntimeError(f"Piper synthesis failed: {stderr or 'unknown error'}")
            audio_bytes = output_path.read_bytes()
            if not audio_bytes:
                raise RuntimeError("Piper did not produce audio")
            return audio_bytes
        finally:
            output_path.unlink(missing_ok=True)

    async def synthesize_speech_stream(
        self,
        text: str,
        *,
        voice: str | None = None,
        rate: str | None = None,
        chunk_size: int = 16384,
    ):
        del voice
        clean_text = " ".join(text.split()).strip()
        if not clean_text:
            return

        self._ensure_piper_assets()
        length_scale = self._rate_to_length_scale(rate or TTS_RATE)

        command = [
            str(PIPER_BINARY_PATH),
            "--model",
            str(PIPER_VOICE_MODEL_PATH),
            "--config",
            str(PIPER_VOICE_CONFIG_PATH),
            "--length_scale",
            f"{length_scale:.3f}",
        ]
        
        env = os.environ.copy()
        ld_paths = [str(PIPER_BIN_DIR)]
        if existing := env.get("LD_LIBRARY_PATH"):
            ld_paths.append(existing)
        env["LD_LIBRARY_PATH"] = ":".join(ld_paths)

        import asyncio
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=str(PIPER_BIN_DIR),
        )
        
        if process.stdin:
            process.stdin.write(clean_text.encode("utf-8"))
            process.stdin.write(b"\n")
            process.stdin.close()
            await process.stdin.wait_closed()

        if process.stdout:
            while True:
                chunk = await process.stdout.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        
        await process.wait()
        if process.returncode != 0:
            err = ""
            if process.stderr:
                err = (await process.stderr.read()).decode("utf-8", errors="ignore").strip()
            raise RuntimeError(f"Piper streaming failed: {err}")

    def _ensure_piper_assets(self) -> None:
        with self._lock:
            if self._piper_ready and PIPER_BINARY_PATH.exists() and PIPER_VOICE_MODEL_PATH.exists():
                return

            if not PIPER_BINARY_PATH.exists():
                self._download_file(PIPER_ARCHIVE_URL, PIPER_ARCHIVE_PATH)
                with tarfile.open(PIPER_ARCHIVE_PATH, "r:gz") as archive:
                    archive.extractall(PIPER_ROOT)
                PIPER_BINARY_PATH.chmod(0o755)

            if not PIPER_VOICE_MODEL_PATH.exists():
                self._download_file(PIPER_VOICE_MODEL_URL, PIPER_VOICE_MODEL_PATH)
            if not PIPER_VOICE_CONFIG_PATH.exists():
                self._download_file(PIPER_VOICE_CONFIG_URL, PIPER_VOICE_CONFIG_PATH)

            self._piper_ready = True

    def _download_file(self, url: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            return
        with urllib.request.urlopen(url, timeout=300) as response:
            destination.write_bytes(response.read())

    def _get_model(self) -> WhisperModel:
        with self._lock:
            if self._stt_model is None:
                try:
                    self._stt_model = self._build_model(STT_DEVICE, STT_COMPUTE_TYPE)
                    self._stt_device = STT_DEVICE
                    self._stt_compute_type = STT_COMPUTE_TYPE
                except Exception:
                    self._stt_model = self._build_model("cpu", "int8")
                    self._stt_device = "cpu"
                    self._stt_compute_type = "int8"
        return self._stt_model

    def _switch_to_cpu_model(self) -> WhisperModel:
        with self._lock:
            self._stt_model = self._build_model("cpu", "int8")
            self._stt_device = "cpu"
            self._stt_compute_type = "int8"
            return self._stt_model

    def _build_model(self, device: str, compute_type: str) -> WhisperModel:
        return WhisperModel(
            STT_MODEL_NAME,
            device=device,
            compute_type=compute_type,
        )

    def _decode_wav(self, audio_bytes: bytes) -> tuple[np.ndarray, float]:
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                channels = wav_file.getnchannels()
                sample_width = wav_file.getsampwidth()
                sample_rate = wav_file.getframerate()
                frame_count = wav_file.getnframes()
                frames = wav_file.readframes(frame_count)
        except wave.Error as exc:
            raise ValueError("Audio must be a PCM WAV file") from exc

        if sample_width not in (1, 2, 4):
            raise ValueError("Unsupported WAV sample width")

        duration_seconds = frame_count / float(sample_rate or 16000)
        if sample_width == 1:
            samples = np.frombuffer(frames, dtype=np.uint8).astype(np.float32)
            samples = (samples - 128.0) / 128.0
        elif sample_width == 2:
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        else:
            samples = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0

        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)

        if sample_rate != 16000:
            samples = self._resample(samples, sample_rate, 16000)

        return samples.astype(np.float32), duration_seconds

    def _resample(self, samples: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
        if len(samples) == 0 or source_rate == target_rate:
            return samples
        target_length = int(round(len(samples) * target_rate / source_rate))
        source_positions = np.linspace(0, len(samples) - 1, num=len(samples), dtype=np.float32)
        target_positions = np.linspace(0, len(samples) - 1, num=max(target_length, 1), dtype=np.float32)
        return np.interp(target_positions, source_positions, samples).astype(np.float32)

    def _rate_to_length_scale(self, rate: str) -> float:
        if not rate:
            return 1.0
        cleaned = rate.strip()
        if cleaned.endswith("%"):
            try:
                percent = float(cleaned[:-1])
            except ValueError:
                return 1.0
            return max(0.5, min(2.0, 1.0 - (percent / 100.0)))
        return 1.0


speech_service = SpeechService()
