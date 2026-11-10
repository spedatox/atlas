"""Launch the Windows SSH client in its own interactive console."""
import os
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalServer


class _PasswordPipe(QLocalServer):
    """Plink's -pwfile reads from this same-user, single-use Windows named pipe."""

    def __init__(self, password, parent):
        super().__init__(parent)
        self._line = password.encode('utf-8') + b'\n'
        self.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        self.newConnection.connect(self._send_password)
        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self.dispose)
        if not self.listen('atlas-ssh-' + uuid4().hex):
            self.dispose()
            raise OSError('SSH parolası için yerel bağlantı açılamadı.')
        self._timeout.start(15000)

    def _send_password(self):
        socket = self.nextPendingConnection()
        if socket is None or not self._line:
            return
        self.close()
        socket.disconnected.connect(self.dispose)
        socket.write(self._line)
        self._line = b''
        socket.disconnectFromServer()

    def dispose(self):
        self._timeout.stop()
        self._line = b''
        self.close()
        self.deleteLater()


def _find_plink():
    app_dir = Path(sys.executable if getattr(sys, 'frozen', False) else __file__).resolve().parent
    candidates = [app_dir / 'plink.exe']
    for env in ('ProgramFiles', 'ProgramFiles(x86)'):
        if os.environ.get(env):
            candidates.append(Path(os.environ[env]) / 'PuTTY' / 'plink.exe')
    for path in candidates:
        if path.is_file():
            return str(path)
    path = shutil.which('plink.exe')
    if path:
        return path
    raise OSError('Kayıtlı parola ile bağlanmak için PuTTY Plink gerekli. PuTTY’yi yükleyin veya plink.exe dosyasını ATLAS’ın yanına koyun.')


def _plink_command(executable, profile, pipe_name):
    return [executable, '-ssh', '-batch', '-t', '-noagent', '-a', '-x', '-noshare',
            '-hostkey', profile.fingerprint, '-P', str(profile.port), '-l', profile.username,
            '-pwfile', pipe_name, profile.host]


def _openssh_command(executable, profile):
    command = [executable, '-tt', '-o', 'StrictHostKeyChecking=ask', '-o', 'ForwardAgent=no',
               '-o', 'ForwardX11=no', '-o', 'ClearAllForwardings=yes',
               '-p', str(profile.port), '-l', profile.username]
    if profile.key_path:
        key = Path(profile.key_path).expanduser()
        if not key.is_absolute() or str(key).startswith(('\\\\', '//')) or not key.is_file():
            raise ValueError('Bu bilgisayarda bulunan bir yerel SSH özel anahtar dosyası seçin.')
        command.extend(('-i', str(key), '-o', 'IdentitiesOnly=yes'))
    return [*command, '--', profile.host]


def launch_ssh(profile, parent):
    if os.name != 'nt':
        raise OSError('Bu sürüm SSH konsolunu Windows üzerinde açar.')

    pipe = None
    if profile.auth == 'password':
        executable = _find_plink()
        pipe = _PasswordPipe(profile.password, parent)
        command = _plink_command(executable, profile, pipe.fullServerName())
    else:
        system_ssh = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32' / 'OpenSSH' / 'ssh.exe'
        executable = str(system_ssh) if system_ssh.is_file() else shutil.which('ssh.exe')
        if not executable:
            raise OSError('Windows OpenSSH İstemcisi bulunamadı. Windows İsteğe Bağlı Özellikler bölümünden yükleyin.')
        command = _openssh_command(executable, profile)
    try:
        return subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_CONSOLE)
    except OSError:
        if pipe is not None:
            pipe.dispose()
        raise
