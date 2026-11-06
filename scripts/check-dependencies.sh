#!/usr/bin/env bash
set -euo pipefail
# check-dependencies.sh: verify everything anicursor needs
#
# Layers:
#   Layer 1  Command check (python3, gsettings, win2xcur)
#   Layer 2  PATH fix: moved to bin/anicursor, not done in this script
#   Layer 3  GTK 4 Python bindings check
#   Layer 4  Library check (libmagickwand-dev)
#   Layer 5  Report with install hints (report only, never installs)
#   Layer 6  Exit code (0 = all present, 1 = something missing)
#
# NOTE: this script expects PATH to be prepared by bin/anicursor.
# If you run it directly, win2xcur may be reported missing even when it is
# installed in ~/.local/bin.

declare -A APT_PACKAGE=(
    [python3]="python3"
    [gsettings]="libglib2.0-bin"
    [gtk4]="python3-gi gir1.2-gtk-4.0"
    [libmagickwand-dev]="libmagickwand-dev"
)
print_install() {
    local apt_packages=()
    local need_win2xcur=false
    local item
    local pkgs
    for item in "$@"; do
        if [[ $item == "win2xcur" ]]; then
            need_win2xcur=true
        elif [[ -n "${APT_PACKAGE[$item]:-}" ]]; then
            read -ra pkgs <<< "${APT_PACKAGE[$item]}"
            apt_packages+=("${pkgs[@]}")    
        else
            echo "Warning: Unknown dependency '$item'" >&2
        fi
    done
    if [[ "$need_win2xcur" == true ]] && (! command -v pipx)  >/dev/null 2>&1; then
        apt_packages+=("pipx")
    fi

    if (( ${#apt_packages[@]} >0 )); then
        echo "Install missing APT packages with:" >&2
        echo "  sudo apt install ${apt_packages[*]}" >&2
    fi

    if [[ "$need_win2xcur" == true ]]; then
        echo "Install win2xcur using pipx:" >&2
        echo "  pipx install win2xcur" >&2
        if (! command -v pipx)  >/dev/null 2>&1; then
            echo "Note: If you just installed pipx, run 'pipx ensurepath' and restart your terminal first." >&2
        fi
    fi
}

check_deps() {
    local commands=(python3 gsettings win2xcur)
    local missing=() # stores missing dependencies for the report

    # --- Layer 1: command check ---
    # Collect every missing command instead of stopping at the first one.
    for cmd in "${commands[@]}"; do
        if (! command -v "$cmd") > /dev/null 2>&1; then
            missing+=("$cmd")
        fi
    done
    # "command -v "$cmd" > /dev/null 2>&1" runs at System Shell / OS Binaries
    # > /dev/null 2>&1  this won't print normal and error output

    # --- Layer 3: GTK 4 Python bindings check ---
    if command -v python3 >/dev/null 2>&1; then
        if (! python3 -c 'import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk') 2>/dev/null; then
            # the above python3 command runs at Python Runtime Environment
            # 2>/dev/null   this won't print error output but normal output would still appear
            missing+=("gtk4")
        fi
    fi

    # --- Layer 4: library check ---
    # win2xcur depends on libmagickwand-dev, which is an APT package, not a command like python3, gsettings, etc.
    if (! dpkg -s libmagickwand-dev) >/dev/null 2>&1; then
        # dpkg -s displays information about an installed Debian package
        missing+=("libmagickwand-dev")
    fi

    # --- Layer 5: report with install hints ---
    if (( "${#missing[@]}" > 0 )); then
        echo "Missing: ${missing[*]}" >&2
        print_install "${missing[@]}"
    fi

    # --- Layer 6: exit code ---
    if [ "${#missing[@]}" == 0 ]; then
        return 0
    else
        echo "${#missing[@]} dependencies are missing." >&2
        return 1
    fi
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    check_deps
fi