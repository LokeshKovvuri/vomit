"""
Windows service wrapper — runs the vomit agent in the background.

Install (as Administrator):
    python agent_win.py install
    python agent_win.py start

Remove:
    python agent_win.py stop
    python agent_win.py remove

Configure by editing agent\\service.env (SESSION_ID and SERVER_URL).

Note: the service is visible in services.msc and Task Manager.
It is not hidden from the operating system.
"""
import subprocess
import sys
from pathlib import Path

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
except ImportError:
    print("pywin32 required: pip install pywin32")
    sys.exit(1)

BASE = Path(__file__).parent.resolve()
ENV_FILE = BASE / "service.env"


def load_env():
    cfg = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                cfg[k.strip()] = v.strip()
    return cfg


class VomitAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = "VomitAgent"
    _svc_display_name_ = "Vomit Remote Agent"
    _svc_description_ = "Background remote-support agent."

    def __init__(self, args):
        super().__init__(args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self.proc = None

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogInfoMsg("VomitAgent starting")
        cfg = load_env()
        session = cfg.get("SESSION_ID", "")
        server = cfg.get("SERVER_URL", "")

        if not session or not server:
            servicemanager.LogErrorMsg("SESSION_ID or SERVER_URL missing in service.env")
            return

        pythonw = sys.executable.replace("python.exe", "pythonw.exe")
        cmd = [pythonw, str(BASE / "agent.py"),
               "--session", session, "--server", server]

        self.proc = subprocess.Popen(
            cmd,
            cwd=str(BASE),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(VomitAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(VomitAgentService)