from __future__ import annotations

import ctypes
import os
import re
import subprocess
import time
import webbrowser
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable
from urllib.parse import quote_plus

import pyautogui
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from ctypes import POINTER, cast

from app.core.models import AppConfig, WindowMatch


EventSink = Callable[[str], None]


class SystemService:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05

    def update_config(self, config: AppConfig) -> None:
        self.config = config

    def resolve_website_url(self, target: str) -> str:
        candidate = target.strip()
        lowered = candidate.lower()

        if lowered in self.config.known_websites:
            return self.config.known_websites[lowered]
        if lowered.startswith(("http://", "https://")):
            return candidate
        if lowered.startswith("www."):
            return f"https://{candidate}"
        if "." in lowered and " " not in lowered:
            return f"https://{candidate}"
        raise ValueError(f"I do not recognize '{target}' as a website target.")

    def open_website(self, target: str, emit: EventSink | None = None) -> str:
        url = self.resolve_website_url(target)
        self._emit(emit, f"Opening website {url}")
        webbrowser.open(url)
        return url

    def search_google(self, query: str, emit: EventSink | None = None) -> str:
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        self._emit(emit, f"Searching Google for {query}")
        webbrowser.open(url)
        return url

    def search_youtube(self, query: str, emit: EventSink | None = None) -> str:
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        self._emit(emit, f"Searching YouTube for {query}")
        webbrowser.open(url)
        return url

    def open_application(self, app_name: str, emit: EventSink | None = None) -> str:
        alias = self._resolve_app_alias(app_name)
        self._emit(emit, f"Opening application {app_name}")

        if alias.lower().startswith(("http://", "https://")):
            webbrowser.open(alias)
            return alias

        alias_path = Path(alias).expanduser()
        if alias_path.exists():
            os.startfile(str(alias_path))
            return str(alias_path)

        try:
            subprocess.Popen([alias], shell=False)
            return alias
        except FileNotFoundError as exc:
            raise RuntimeError(
                f"I could not launch '{app_name}'. Add or adjust it in config/settings.json under app_aliases."
            ) from exc

    def create_folder(self, folder_name: str, location: str, emit: EventSink | None = None) -> Path:
        target = self.build_target_path(folder_name, location, allow_extension=False)
        self._guard_path(target)
        target.mkdir(parents=False, exist_ok=False)
        self._emit(emit, f"Created folder {target}")
        return target

    def create_file(self, file_name: str, location: str, emit: EventSink | None = None) -> Path:
        target = self.build_target_path(file_name, location, allow_extension=True)
        self._guard_path(target)
        target.touch(exist_ok=False)
        self._emit(emit, f"Created file {target}")
        return target

    def build_target_path(self, item_name: str, location: str, allow_extension: bool) -> Path:
        expanded_name = os.path.expandvars(item_name.strip())
        candidate = Path(expanded_name).expanduser()
        if self._looks_like_path(expanded_name):
            target = candidate if candidate.is_absolute() else (Path.cwd() / candidate)
            leaf = target.name
            self._validate_windows_name(leaf, allow_extension=allow_extension)
            return target.resolve(strict=False)

        self._validate_windows_name(expanded_name, allow_extension=allow_extension)
        base_dir = self.resolve_location(location)
        return (base_dir / expanded_name).resolve(strict=False)

    def take_screenshot(self, emit: EventSink | None = None) -> Path:
        output_dir = Path(self.config.screenshot_directory).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"screenshot_{datetime.now():%Y%m%d_%H%M%S}.png"
        self._emit(emit, "Capturing screenshot")
        image = pyautogui.screenshot()
        image.save(target)
        return target

    def get_time_text(self) -> str:
        return datetime.now().strftime("%H:%M")

    def get_date_text(self) -> str:
        return datetime.now().strftime("%A, %d %B %Y")

    def change_volume(self, delta_percent: int, emit: EventSink | None = None) -> int:
        endpoint = self._volume_endpoint()
        current = endpoint.GetMasterVolumeLevelScalar()
        updated = self._clamp(current + (delta_percent / 100.0), 0.0, 1.0)
        endpoint.SetMute(0, None)
        endpoint.SetMasterVolumeLevelScalar(updated, None)
        percent = round(updated * 100)
        self._emit(emit, f"Volume set to {percent}%")
        return percent

    def set_volume(self, percent: int, emit: EventSink | None = None) -> int:
        endpoint = self._volume_endpoint()
        target = self._clamp(percent / 100.0, 0.0, 1.0)
        endpoint.SetMute(0, None)
        endpoint.SetMasterVolumeLevelScalar(target, None)
        actual = round(target * 100)
        self._emit(emit, f"Volume set to {actual}%")
        return actual

    def mute(self, emit: EventSink | None = None) -> None:
        endpoint = self._volume_endpoint()
        endpoint.SetMute(1, None)
        self._emit(emit, "Volume muted")

    def unmute(self, emit: EventSink | None = None) -> None:
        endpoint = self._volume_endpoint()
        endpoint.SetMute(0, None)
        self._emit(emit, "Volume unmuted")

    def schedule_shutdown(self, emit: EventSink | None = None) -> int:
        delay = max(0, int(self.config.system_action_delay_seconds))
        self._emit(emit, f"Scheduling shutdown in {delay} seconds")
        subprocess.run(["shutdown", "/s", "/t", str(delay)], check=True, capture_output=True)
        return delay

    def schedule_restart(self, emit: EventSink | None = None) -> int:
        delay = max(0, int(self.config.system_action_delay_seconds))
        self._emit(emit, f"Scheduling restart in {delay} seconds")
        subprocess.run(["shutdown", "/r", "/t", str(delay)], check=True, capture_output=True)
        return delay

    def cancel_pending_shutdown(self, emit: EventSink | None = None) -> None:
        self._emit(emit, "Attempting to cancel pending shutdown or restart")
        subprocess.run(["shutdown", "/a"], check=True, capture_output=True)

    def lock_pc(self, emit: EventSink | None = None) -> None:
        self._emit(emit, "Locking the workstation")
        if not ctypes.windll.user32.LockWorkStation():
            raise RuntimeError("Windows refused to lock the workstation.")

    def type_text(self, text: str, emit: EventSink | None = None) -> None:
        delay = max(0, int(self.config.typing_delay_seconds))
        self._emit(emit, f"Typing will start in {delay} seconds")
        time.sleep(delay)
        pyautogui.write(text, interval=0.015)
        self._emit(emit, "Finished typing text")

    def move_mouse(self, direction: str, distance: int, emit: EventSink | None = None) -> tuple[int, int]:
        safe_distance = max(1, min(abs(distance), int(self.config.mouse_max_distance)))
        delta_x = 0
        delta_y = 0
        direction_key = direction.lower()
        if direction_key == "left":
            delta_x = -safe_distance
        elif direction_key == "right":
            delta_x = safe_distance
        elif direction_key == "up":
            delta_y = -safe_distance
        elif direction_key == "down":
            delta_y = safe_distance
        else:
            raise RuntimeError("Mouse movement direction must be up, down, left, or right.")

        self._emit(emit, f"Moving mouse {direction_key} by {safe_distance} pixels")
        pyautogui.moveRel(delta_x, delta_y, duration=0.2)
        position = pyautogui.position()
        return position.x, position.y

    def click_mouse(self, button: str, emit: EventSink | None = None) -> None:
        selected = button if button in {"left", "right"} else "left"
        self._emit(emit, f"Clicking {selected} mouse button")
        pyautogui.click(button=selected)

    def focus_window(self, target: str, emit: EventSink | None = None) -> WindowMatch:
        match = self.find_window(target)
        if match is None:
            raise RuntimeError(f"Ich konnte kein Fenster finden, das zu '{target}' passt.")
        self._emit(emit, f"Focusing window {match.title}")
        if ctypes.windll.user32.IsIconic(match.handle):
            ctypes.windll.user32.ShowWindow(match.handle, 9)
        if not ctypes.windll.user32.SetForegroundWindow(match.handle):
            raise RuntimeError(f"Windows konnte das Fenster '{match.title}' nicht in den Vordergrund bringen.")
        return match

    def find_window(self, target: str) -> WindowMatch | None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        results: list[WindowMatch] = []
        search = target.strip().lower()

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
        def enum_proc(hwnd, _lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True
            buffer = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value.strip()
            if not title:
                return True

            process_id = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(process_id))
            process_name = ""
            handle = kernel32.OpenProcess(0x0410, False, process_id.value)
            if handle:
                try:
                    name_buffer = ctypes.create_unicode_buffer(260)
                    size = ctypes.c_ulong(len(name_buffer))
                    if ctypes.windll.psapi.GetModuleBaseNameW(handle, None, name_buffer, size):
                        process_name = name_buffer.value
                finally:
                    kernel32.CloseHandle(handle)

            haystack = f"{title} {process_name}".lower()
            if search in haystack:
                score = 0.75 + min(0.24, len(search) / max(len(haystack), 1))
            else:
                score = SequenceMatcher(None, search, haystack).ratio()
            if score >= 0.45:
                results.append(WindowMatch(title=title, handle=int(hwnd), process_name=process_name, score=score))
            return True

        user32.EnumWindows(enum_proc, 0)
        if not results:
            return None
        results.sort(key=lambda item: item.score, reverse=True)
        return results[0]

    def read_clipboard(self, emit: EventSink | None = None) -> str:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
            check=True,
            capture_output=True,
            text=True,
        )
        text = completed.stdout
        self._emit(emit, f"Read {len(text)} characters from clipboard")
        return text

    def write_clipboard(self, text: str, emit: EventSink | None = None) -> int:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", "$text = [Console]::In.ReadToEnd(); Set-Clipboard -Value $text"],
            input=text,
            check=True,
            capture_output=True,
            text=True,
        )
        self._emit(emit, f"Wrote {len(text)} characters to clipboard")
        return len(text)

    def resolve_location(self, location: str) -> Path:
        expanded = os.path.expandvars(location.strip())
        candidate = Path(expanded).expanduser()
        if self._looks_like_path(expanded):
            target = candidate if candidate.is_absolute() else (Path.cwd() / candidate)
            return target.resolve(strict=False)

        normalized = expanded.lower()
        mapping = {
            "current folder": Path.cwd(),
            "current directory": Path.cwd(),
            "desktop": Path.home() / "Desktop",
            "documents": Path.home() / "Documents",
            "downloads": Path.home() / "Downloads",
            "home": Path.home(),
            "music": Path.home() / "Music",
            "pictures": Path.home() / "Pictures",
            "project": Path.cwd(),
            "videos": Path.home() / "Videos",
        }
        if normalized not in mapping:
            raise RuntimeError(f"I do not know the location '{location}'.")
        target = mapping[normalized]
        target.mkdir(parents=True, exist_ok=True)
        return target

    def _resolve_app_alias(self, app_name: str) -> str:
        key = app_name.strip().lower()
        if key in self.config.app_aliases:
            return self.config.app_aliases[key]
        simplified = re.sub(r"\s+", " ", key)
        if simplified in self.config.app_aliases:
            return self.config.app_aliases[simplified]
        return simplified

    def _guard_path(self, path: Path) -> None:
        resolved = path.expanduser().resolve(strict=False)
        if len(resolved.parts) <= 1:
            raise RuntimeError("I will not create items at a drive root.")
        for blocked in self.config.blocked_paths:
            blocked_path = Path(os.path.expandvars(blocked)).expanduser().resolve(strict=False)
            if resolved == blocked_path or blocked_path in resolved.parents:
                raise RuntimeError(f"That path is protected: {blocked_path}")

    def _validate_windows_name(self, name: str, allow_extension: bool) -> None:
        if not name.strip():
            raise RuntimeError("The name cannot be empty.")
        if "/" in name or "\\" in name:
            raise RuntimeError("Use a simple file or folder name, not a nested path.")
        invalid_pattern = r'[<>:"/\\|?*]'
        if re.search(invalid_pattern, name):
            raise RuntimeError("That name contains characters Windows does not allow.")
        if not allow_extension and "." in name:
            raise RuntimeError("Folder names cannot contain dots in this assistant workflow.")

    @staticmethod
    def _looks_like_path(value: str) -> bool:
        return any(
            marker in value
            for marker in ("\\", "/", ":", ".\\", "..\\", "%USERPROFILE%", "%HOMEPATH%")
        )

    def _volume_endpoint(self) -> IAudioEndpointVolume:
        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        return cast(interface, POINTER(IAudioEndpointVolume))

    @staticmethod
    def _clamp(value: float, lower: float, upper: float) -> float:
        return max(lower, min(value, upper))

    @staticmethod
    def _emit(emit: EventSink | None, message: str) -> None:
        if emit:
            emit(message)
