from __future__ import annotations

import json
import queue
import threading
import time
from pathlib import Path

import sounddevice as sd
from vosk import KaldiRecognizer, Model

from app.core.models import AppConfig


class SpeechRecognitionService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._model = None
        self._model_path = ""
        self._stop_event = threading.Event()

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def available_input_devices(self) -> list[dict[str, object]]:
        devices: list[dict[str, object]] = []
        for index, device in enumerate(sd.query_devices()):
            if int(device.get("max_input_channels", 0) or 0) < 1:
                continue
            devices.append(
                {
                    "index": index,
                    "name": str(device.get("name", f"Input {index}")),
                    "channels": int(device.get("max_input_channels", 0) or 0),
                    "samplerate": int(device.get("default_samplerate", 16000) or 16000),
                }
            )
        return devices

    def stop_listening(self) -> None:
        self._stop_event.set()

    def listen_once(self, max_seconds: int = 15) -> str:
        if not self.config.voice_input_enabled:
            raise RuntimeError("Voice input is disabled in settings.")

        model = self._get_model()
        sample_rate = 16000
        recognizer = KaldiRecognizer(model, sample_rate)
        frames: queue.Queue[bytes] = queue.Queue()
        self._stop_event.clear()

        def callback(indata: bytes, _frames: int, _time: object, status: sd.CallbackFlags) -> None:
            if status:
                return
            frames.put(bytes(indata))

        stream_kwargs = {
            "samplerate": sample_rate,
            "blocksize": 8000,
            "dtype": "int16",
            "channels": 1,
            "callback": callback,
        }
        device_index = self._resolve_device_index()
        if device_index is not None:
            stream_kwargs["device"] = device_index

        started = time.monotonic()
        final_text = ""
        with sd.RawInputStream(**stream_kwargs):
            while time.monotonic() - started < max_seconds:
                if self._stop_event.is_set():
                    break
                try:
                    data = frames.get(timeout=0.3)
                except queue.Empty:
                    continue

                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    final_text = result.get("text", "").strip()
                    if final_text:
                        break

        if not final_text:
            result = json.loads(recognizer.FinalResult())
            final_text = result.get("text", "").strip()

        if self._stop_event.is_set() and not final_text:
            raise RuntimeError("Voice capture stopped.")
        if not final_text:
            raise RuntimeError("I could not understand the microphone input.")
        return final_text

    def _get_model(self) -> Model:
        configured_path = self.config.vosk_model_path.strip()
        if not configured_path:
            raise RuntimeError(
                "Voice input needs a local Vosk model. Download one and set 'vosk_model_path' in config/settings.json."
            )

        model_path = Path(configured_path).expanduser()
        if not model_path.exists():
            raise RuntimeError(
                "Voice input needs a local Vosk model. Download one and set 'vosk_model_path' in config/settings.json."
            )
        normalized = str(model_path.resolve())
        if self._model is None or self._model_path != normalized:
            self._model = Model(normalized)
            self._model_path = normalized
        return self._model

    def _resolve_device_index(self) -> int | None:
        desired = self.config.voice_input_device.strip()
        if not desired:
            return None
        for device in self.available_input_devices():
            if str(device["name"]) == desired:
                return int(device["index"])
        return None
