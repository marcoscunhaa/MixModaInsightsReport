"""Uma janela só: a segunda execução avisa a primeira e não abre (precisa do PySide6; roda no CI)."""
import os
import uuid

import pytest

pytest.importorskip("PySide6.QtNetwork")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QElapsedTimer  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from ui import single_instance as si  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def wait_until(condition, ms=3000):
    timer = QElapsedTimer()
    timer.start()
    while not condition() and timer.elapsed() < ms:
        QCoreApplication.processEvents()
    return condition()


def test_second_launch_brings_first_window_forward(app, monkeypatch):
    name = f"MixModaTeste-{uuid.uuid4().hex[:8]}"
    first = si.acquire(name)
    assert first is not None
    window = QWidget()
    window.showMinimized()
    first.window = window
    calls = []
    monkeypatch.setattr(first, "bring_to_front", lambda: calls.append(True))
    monkeypatch.setattr(si, "NOTIFY_WAIT_S", 0.5)

    # A segunda execução encontra a trava, avisa a primeira e não abre nada.
    assert si.acquire(name) is None
    assert wait_until(lambda: bool(calls))
    first.server.close()
    first.lock.unlock()
    window.close()


def test_launch_after_first_closes_opens_normally(app):
    name = f"MixModaTeste-{uuid.uuid4().hex[:8]}"
    first = si.acquire(name)
    first.server.close()
    first.lock.unlock()
    second = si.acquire(name)
    assert second is not None and second.server.isListening()
    second.server.close()
    second.lock.unlock()


def test_bring_to_front_restores_minimized_window(app):
    instance = si.SingleInstance(f"MixModaTeste-{uuid.uuid4().hex[:8]}")
    window = QWidget()
    window.showMinimized()
    instance.window = window
    instance.bring_to_front()
    assert not window.isMinimized() and window.isVisible()
    instance.server.close()
    window.close()
