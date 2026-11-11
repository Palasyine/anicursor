import subprocess, os, json
from dataclasses import dataclass, asdict
from pathlib import Path

@dataclass
class CursorSettings:
    theme: str
    size: int

class SettingsError(Exception):
    pass


SCHEMA = "org.gnome.desktop.interface"

def _gsettings(*args: str) -> str:       # run gsettings, return stripped stdout
    try:
        result=subprocess.run(["gsettings", *args],
                              check=True,
                              capture_output=True,
                              text=True,)
        return result.stdout.strip()
    
    except FileNotFoundError as error1:
        raise SettingsError(
            "The 'gsettings' executable was not found. Are you running on a compatible desktop environment?"
        ) from error1
    
    except subprocess.CalledProcessError as error2:
        err_msg=error2.stderr.strip() if error2.stderr else f"Command failed with exit code {error2.returncode}"
        raise SettingsError(
            f"Failed to execute gsettings {' '.join(args)}: {err_msg}"
        ) from error2
    
    except subprocess.TimeoutExpired as error3:
        raise SettingsError(
            "The gsettings command timed out."
        ) from error3

def _rollback(previous_setting: CursorSettings) -> str:
    try:
        _gsettings("set", SCHEMA, "cursor-theme", previous_setting.theme)
        _gsettings("set", SCHEMA, "cursor-size", previous_setting.size)
    except SettingsError as err:
        return (
            f"rollback also failed ({err}); "
            f"previous values were theme={previous_setting.theme}, size={previous_setting.size}")
    
def get_current() -> CursorSettings:
    current_theme=_gsettings("get", SCHEMA, "cursor-theme").strip("'")
    current_size=_gsettings("get", SCHEMA, "cursor-size")
    try:
        size = int(current_size)
    except ValueError as err:
        raise SettingsError(f"Invalid cursor size returned by gsettings: {current_size}") from err
    
    return CursorSettings(theme=current_theme, size=size)

def apply(theme: str, size: int) -> None:
    if not isinstance(theme, str) or not theme.strip():
        raise SettingsError("theme must be a non-empty string")
    if not isinstance(size, int) or isinstance(size, bool) or size <=0:
        raise SettingsError("size must be a positive integer")
    previous_setting=get_current()
    try:
        _gsettings("set", SCHEMA, "cursor-theme", theme)
        _gsettings("set", SCHEMA, "cursor-size", str(size))
        current_setting=get_current()
    except SettingsError as err:
        raise SettingsError(f"Failed to apply settings: {err} ({_rollback(previous)})") from err
    failed=[]
    if current_setting.theme != theme:
        failed.append("cursor-theme")
    if current_setting.size != size:
        failed.append("cursor-size")  
    if failed:
        raise SettingsError(
            f"gsettings did not keep {' and '.join(failed)} ({_rollback(previous)})"
        )
def backup_path() -> Path:              # XDG state dir
    state_home = Path(
        os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state"
    )
    return state_home / "anicursor" / "backup.json"

def save_backup(settings: CursorSettings, path: Path | None = None) -> bool:       # False if one already exists
    path=path or backup_path()
    try:
        backup_data = json.dumps(asdict(settings), indent=4)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as file:
            file.write(backup_data)

    except FileExistsError:
        return False
    except OSError as err:
        raise SettingsError(f"Failed to save backup: {err}") from err
    return True

def load_backup(path: Path | None = None) -> CursorSettings | None:
    path = path or backup_path()
    if not path.is_file():
        return None
    
    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (ValueError, OSError) as err:
        raise SettingsError(f"Failed to read backup: {err}") from err

    if not isinstance(data, dict):
        raise SettingsError("Invalid backup format")

    backup_theme = data.get("theme")
    backup_size = data.get("size")

    if not isinstance(backup_theme, str) or not backup_theme.strip():
        raise SettingsError("Backup theme must be a non-empty string")

    if not isinstance(backup_size, int) or isinstance(backup_size, bool) or backup_size <= 0:
        raise SettingsError("Backup size must be a positive integer")
    #extra bool checking because "isinstance(True, int)"  will return True

    return CursorSettings(theme=backup_theme, size=int(backup_size))

def restore(path: Path | None = None) -> CursorSettings:
    backup_setting=load_backup(path)
    if backup_setting is None:
        raise SettingsError("No backup exists")
    apply(backup_setting.theme, backup_setting.size)
    return backup_setting