import pytest, subprocess, json
import anicursor.settings as settings_module
from dataclasses import asdict
from pathlib import Path

from anicursor.settings import (
    CursorSettings,
    SettingsError,
    _gsettings,
    get_current,
    backup_path,
    save_backup,
    load_backup,
    restore,
    SCHEMA,

)
from types import SimpleNamespace

# _gsettings tests

def test_gsettings_success(monkeypatch):
    def fake_run(*args, **kwargs):
        return SimpleNamespace(stdout="Herta\n")

    monkeypatch.setattr(settings_module.subprocess, "run", fake_run)

    assert _gsettings("get", SCHEMA, "cursor-theme") == "Herta"


def test_gsettings_missing(monkeypatch):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("gsettings not found")

    monkeypatch.setattr(settings_module.subprocess, "run", fake_run)

    with pytest.raises(SettingsError):
        _gsettings("get", SCHEMA, "cursor-theme")


def test_gsettings_failure(monkeypatch):
    def fake_run(*args, **kwargs):
        raise subprocess.CalledProcessError(
            returncode=1,
            cmd=args[0],
            stderr="Invalid gsettings key",
        )

    monkeypatch.setattr(settings_module.subprocess, "run", fake_run)

    with pytest.raises(SettingsError):
        _gsettings("get", SCHEMA, "cursor-theme")


# get_current tests

def test_get_current(monkeypatch):
    def fake_run(*args, **kwargs):
        if args[0][-1] == "cursor-theme":
            return SimpleNamespace(stdout="'Herta'\n")
        elif args[0][-1] == "cursor-size":
            return SimpleNamespace(stdout="48\n")

    monkeypatch.setattr(settings_module.subprocess, "run", fake_run)

    result = get_current()

    assert result.theme == "Herta"
    assert result.size == 48
    assert isinstance(result.size, int)


# backup_path tests

def test_backup_path_default(monkeypatch):
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.setattr(Path, "home", lambda: Path("/home/testuser"))

    assert backup_path() == Path(
        "/home/testuser/.local/state/anicursor/backup.json"
    )


def test_backup_path_custom_xdg_state_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))

    assert backup_path() == tmp_path / "anicursor" / "backup.json"


def test_backup_path_empty_xdg_state_home(monkeypatch):
    monkeypatch.setenv("XDG_STATE_HOME", "")
    monkeypatch.setattr(Path, "home", lambda: Path("/home/testuser"))

    assert backup_path() == Path(
        "/home/testuser/.local/state/anicursor/backup.json"
    )


# save_backup tests

def test_save_backup_no_existing_backup(tmp_path):
    path = tmp_path / "anicursor" / "backup.json"
    settings = CursorSettings(theme="Adwaita", size=24)

    result = save_backup(settings, path)

    assert result is True
    assert path.is_file()

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == asdict(settings)


def test_save_backup_already_exists(tmp_path):
    path = tmp_path / "anicursor" / "backup.json"
    path.parent.mkdir(parents=True)

    original_data = {"theme": "Original", "size": 24}
    path.write_text(json.dumps(original_data), encoding="utf-8")

    settings = CursorSettings(theme="Adwaita", size=32)

    result = save_backup(settings, path)

    assert result is False

    saved_data = json.loads(path.read_text(encoding="utf-8"))
    assert saved_data == original_data


def test_save_and_load_backup_round_trip(tmp_path):
    path = tmp_path / "anicursor" / "backup.json"
    original = CursorSettings(theme="Adwaita", size=24)

    assert save_backup(original, path) is True

    restored = load_backup(path)

    assert restored == original


# load_backup tests

def test_load_backup_no_existing_backup(tmp_path):
    path = tmp_path / "backup.json"

    result = load_backup(path)

    assert result is None


def test_load_backup_valid_file(tmp_path):
    path = tmp_path / "backup.json"
    data = {"theme": "Adwaita", "size": 24}
    path.write_text(json.dumps(data), encoding="utf-8")

    result = load_backup(path)

    assert result == CursorSettings(theme="Adwaita", size=24)

def test_load_backup_invalid_utf8(tmp_path):
    path = tmp_path / "backup.json"
    path.write_bytes(b"\xff\xfe\xfa")

    with pytest.raises(SettingsError, match="Failed to read backup"):
        load_backup(path)

@pytest.mark.parametrize("content", [
    "{invalid json",
    "[]",
    "null",
    '{"theme": "Adwaita"}',
    '{"theme": "", "size": 24}',
    '{"theme": "Adwaita", "size": -1}',
    '{"theme": "Adwaita", "size": true}',
])
def test_load_backup_corrupted_or_invalid_data(tmp_path, content):
    path = tmp_path / "backup.json"
    path.write_text(content, encoding="utf-8")

    with pytest.raises(SettingsError):
        load_backup(path)


# restore tests

def test_restore_existing_backup(tmp_path, monkeypatch):
    path = tmp_path / "backup.json"
    data = {"theme": "Adwaita", "size": 24}
    path.write_text(json.dumps(data), encoding="utf-8")

    calls = []

    def fake_gsettings(*args):
        calls.append(args)
        if args[0] == "get":
            if args[-1] == "cursor-theme":
                return "Adwaita"
            elif args[-1] == "cursor-size":
                return "24"

    monkeypatch.setattr(settings_module, "_gsettings", fake_gsettings)

    result = restore(path)

    assert result == CursorSettings(theme="Adwaita", size=24)

    assert calls == [
        ("get", SCHEMA, "cursor-theme"),
        ("get", SCHEMA, "cursor-size"),
        ("set", SCHEMA, "cursor-theme", "Adwaita"),
        ("set", SCHEMA, "cursor-size", "24"),
        ("get", SCHEMA, "cursor-theme"),
        ("get", SCHEMA, "cursor-size"),
    ]

    # The backup is retained after successful restoration.
    assert path.is_file()


def test_restore_no_existing_backup(tmp_path):
    path = tmp_path / "backup.json"

    with pytest.raises(SettingsError):
        restore(path)
