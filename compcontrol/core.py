"""Deterministic command routing. Never evaluates user text as code or shell input."""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Callable


@dataclass(frozen=True)
class Result:
    message: str
    action: str = "none"
    confirmation_required: bool = False


@dataclass(frozen=True)
class Intent:
    name: str
    description: str
    handler: Callable[[], Result]


def _open_calculator() -> Result:
    if platform.system() != "Windows":
        return Result("Opening Calculator is currently supported on Windows only.")
    try:
        # Fixed executable and no shell: user text cannot influence process arguments.
        subprocess.Popen(["calc.exe"], shell=False, close_fds=(os.name != "nt"))
    except OSError:
        return Result("Could not start Calculator. Check that Windows Calculator is available.")
    return Result("Opened Calculator.", action="open_calculator")


class Assistant:
    """Small allowlisted intent router; unknown requests have no side effects."""

    def __init__(self) -> None:
        self._intents = {
            "help": Intent("help", "Show supported commands", self._help),
            "time": Intent("time", "Show the local time", self._time),
            "open calculator": Intent("open calculator", "Open Windows Calculator", _open_calculator),
        }

    @staticmethod
    def _help() -> Result:
        return Result("Try: help, time, or open calculator.")

    @staticmethod
    def _time() -> Result:
        return Result(datetime.now().astimezone().strftime("Local time: %Y-%m-%d %H:%M:%S %Z"))

    def handle(self, text: str) -> Result:
        normalized = " ".join(text.strip().lower().split())
        if not normalized:
            return Result("Type a command, or try help.")
        intent = self._intents.get(normalized)
        if intent is None:
            return Result("I don't support that command yet. No action was taken. Try help.")
        return intent.handler()
