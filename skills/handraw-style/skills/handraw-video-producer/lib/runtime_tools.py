"""Resolve local runtimes consistently; never install or download implicitly."""
import os
from pathlib import Path
import shutil


def executable(name):
    value = os.environ.get('HVP_' + name.upper()) or shutil.which(name)
    if not value:
        raise RuntimeError('Missing runtime: ' + name + '; install it on PATH or set HVP_' + name.upper())
    return value


def browser_executable():
    """Discover an installed browser; never download one during rendering."""
    configured = os.environ.get('HVP_BROWSER')
    if configured:
        if not Path(configured).is_file():
            raise RuntimeError('HVP_BROWSER does not point to an existing browser')
        return configured
    for name in ('msedge', 'chrome', 'chromium', 'chromium-browser', 'google-chrome'):
        value = shutil.which(name)
        if value:
            return value
    for key in ('PROGRAMFILES(X86)', 'PROGRAMFILES', 'LOCALAPPDATA'):
        folder = os.environ.get(key)
        if folder:
            for relative in ('Microsoft/Edge/Application/msedge.exe', 'Google/Chrome/Application/chrome.exe'):
                value = Path(folder)/relative
                if value.is_file():
                    return str(value)
    raise RuntimeError('Missing browser; install Edge/Chrome/Chromium or set HVP_BROWSER')


def browser_launch_options():
    channel = os.environ.get('HVP_BROWSER_CHANNEL')
    if channel and not os.environ.get('HVP_BROWSER'):
        return {'channel': channel}
    return {'executable_path': browser_executable()}
