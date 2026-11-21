"""Uma janela só: abrir o app de novo traz a janela que já está aberta para a frente.

Duas janelas abertas guardam, cada uma, o catálogo do momento em que abriram; a
que gravasse por último apagaria os cadastros da outra. A primeira execução abre
um canal local (QLocalServer); a segunda encontra o canal, pede para a primeira
aparecer e fecha sem abrir janela.

Um arquivo de trava (QLockFile) decide quem é a primeira, mesmo quando as duas
execuções começam quase juntas (dois cliques seguidos no .exe).
"""
import getpass
import hashlib
import os
import tempfile
import time

from PySide6.QtCore import QLockFile, QObject, Qt
from PySide6.QtNetwork import QLocalServer, QLocalSocket

SHOW_MESSAGE = b"show"
TIMEOUT_MS = 1000
# A primeira execução pode ainda estar abrindo o canal: a segunda tenta por até 5 s.
NOTIFY_WAIT_S = 5.0


def server_name(app_id="MixModaInsights"):
    """Nome do canal: um por usuário do Windows, sem caracteres especiais."""
    try:
        user = getpass.getuser()
    except Exception:
        user = "usuario"
    digest = hashlib.sha1(f"{app_id}:{user}".encode("utf-8")).hexdigest()[:12]
    return f"{app_id}-{digest}"


def notify_running_instance(name):
    """True se já há uma janela aberta: ela é avisada para aparecer."""
    socket = QLocalSocket()
    socket.connectToServer(name)
    if not socket.waitForConnected(TIMEOUT_MS):
        return False
    socket.write(SHOW_MESSAGE)
    socket.flush()
    socket.waitForBytesWritten(TIMEOUT_MS)
    socket.disconnectFromServer()
    return True


class SingleInstance(QObject):
    """Canal da primeira execução. `window` é a janela que aparece quando o app é aberto de novo."""

    def __init__(self, name, lock=None, parent=None):
        super().__init__(parent)
        self.name = name
        self.lock = lock  # mantém a trava enquanto o app estiver aberto
        self.window = None
        self.server = QLocalServer(self)
        self.server.newConnection.connect(self._on_connection)
        if not self.server.listen(name) and lock is not None:
            # Com a trava na mão, o canal só pode ter sobrado de uma execução que caiu
            # (Linux/macOS): limpa e tenta de novo.
            QLocalServer.removeServer(name)
            self.server.listen(name)

    def _on_connection(self):
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()
            socket.readyRead.connect(socket.readAll)
            socket.disconnected.connect(socket.deleteLater)
            self.bring_to_front()

    def bring_to_front(self):
        window = self.window
        if window is None:
            return
        if window.isMinimized():
            window.showNormal()
        window.show()
        window.setWindowState((window.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        window.raise_()
        window.activateWindow()


def lock_path(name):
    return os.path.join(tempfile.gettempdir(), f"{name}.lock")


def acquire(name=None):
    """None se o app já está aberto (a janela existente foi avisada); senão, o canal desta execução."""
    name = name or server_name()
    lock = QLockFile(lock_path(name))
    lock.setStaleLockTime(0)  # trava de execução que caiu é detectada pelo PID, não pelo tempo
    if not lock.tryLock(0):
        lock.removeStaleLockFile()
        if not lock.tryLock(0):
            deadline = time.monotonic() + NOTIFY_WAIT_S
            while time.monotonic() < deadline:
                if notify_running_instance(name):
                    return None
                time.sleep(0.2)
            # A trava existe mas ninguém respondeu: não impede o usuário de abrir o app.
            lock = None
    return SingleInstance(name, lock)
