from __future__ import annotations

import threading

import pyttsx3

from app.core.models import AppConfig


class TextToSpeechService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._engine = None
        self._lock = threading.Lock()

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def _engine_instance(self) -> pyttsx3.Engine:
        if self._engine is None:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", 185)
            self._engine.setProperty("volume", 0.9)
        return self._engine

    def speak(self, text: str) -> None:
        if not self.config.voice_output_enabled or not text.strip():
            return
        with self._lock:
            engine = self._engine_instance()
            engine.say(text)
            engine.runAndWait()
