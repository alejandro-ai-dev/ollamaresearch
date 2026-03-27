"""Notificaciones de escritorio multiplataforma."""
import platform
import subprocess


def notify(title: str, body: str) -> None:
    """Envía una notificación de escritorio si es posible. Falla silenciosamente."""
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.run(
                ["notify-send", "--app-name=OllamaResearch", title, body],
                check=False, timeout=3,
            )
        elif system == "Darwin":
            script = f'display notification "{body}" with title "{title}" sound name "Glass"'
            subprocess.run(["osascript", "-e", script], check=False, timeout=3)
        elif system == "Windows":
            ps = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$n = New-Object System.Windows.Forms.NotifyIcon; "
                "$n.Icon = [System.Drawing.SystemIcons]::Information; "
                "$n.Visible = $true; "
                f'$n.ShowBalloonTip(5000, "{title}", "{body}", '
                "[System.Windows.Forms.ToolTipIcon]::Info); "
                "Start-Sleep -s 5; $n.Dispose()"
            )
            subprocess.Popen(
                ["powershell", "-WindowStyle", "Hidden", "-Command", ps],
                creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
            )
    except Exception:
        pass
