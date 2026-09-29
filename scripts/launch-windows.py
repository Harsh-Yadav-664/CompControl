"""One-shot source launcher. No installation, elevation, downloads or HTTP server."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def command(python, root, widget=False):
    pythonw = Path(python).with_name('pythonw.exe')
    if not pythonw.is_file():
        raise ValueError('pythonw.exe is missing. Install standard Windows Python with Tcl/Tk from python.org.')
    return [str(pythonw), str(root / 'scripts' / 'start-windows.pyw'), *(['--widget'] if widget else [])]


def main():
    parser = argparse.ArgumentParser(description='Start the native CompControl window, never the browser UI.')
    parser.add_argument('--widget', action='store_true')
    parser.add_argument('--diagnose', action='store_true')
    args = parser.parse_args()
    print('CompControl source folder: ' + str(ROOT))
    if sys.platform != 'win32':
        print('This launcher is for Windows. It must run on your PC, not in the browser preview.')
        return 1
    if sys.version_info < (3, 10):
        print('Install Python 3.10 or newer (Python 3.12 recommended for this source package).')
        return 1
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    try:
        from compcontrol import __version__
        from compcontrol.planner import plan_request
        from compcontrol.models import Action
        expected = Action('search', 'youtube', 'mr whose the boss')
        if plan_request('open yt and search for mr whose the boss').actions != (expected,):
            raise ValueError('The local files do not include the YouTube fix. Extract the current source ZIP to a new folder.')
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        argv = command(sys.executable, ROOT, args.widget)
        print('Version: ' + __version__ + ' | Native desktop | Tcl/Tk OK | YouTube parser OK')
        if args.diagnose:
            print('Preflight passed. No AI request or desktop action was performed.')
            return 0
        subprocess.Popen(argv, cwd=str(ROOT), shell=False, close_fds=True)
    except ImportError:
        print('Python Tcl/Tk or CompControl files are missing. Extract the WHOLE ZIP; then modify/reinstall '
              'Windows Python with the tcl/tk and IDLE option enabled. No pip install is needed.')
        return 1
    except (OSError, ValueError) as exc:
        print('Could not launch: ' + str(exc))
        return 1
    except Exception:
        print('Native UI preflight failed. Run py -3 -m tkinter to check your desktop Python installation.')
        return 1
    print('Native window launched. This console can close. No browser interface was started.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
