#!/usr/bin/env bash
set -euo pipefail
# check-dependencies.sh: verify everything anicursor needs
#
# Layers:
#   Layer 1  Command check (python3, gsettings, win2xcur, pipx)
#   Layer 2  PATH fix: moved to bin/anicursor, not done in this script
#   Layer 3  GTK 4 Python bindings check
#   Layer 4  Library check (libmagickwand-dev)
#   Layer 5  Report with install hints (report only, never installs)
#   Layer 6  Exit code (0 = all present, 1 = something missing)
#
# NOTE: this script expects PATH to be prepared by bin/anicursor.
# If you run it directly, win2xcur may be reported missing even when it is
# installed in ~/.local/bin.

check_deps() {
    local commands=(python3 gsettings win2xcur pipx)
    local missing_commands=() # stores missing commands for the report
    local missing_components=() # separate array because GTK 4 Python bindings aren't an executable command like python3 or win2xcur

    echo "Checking dependencies..."

    # --- Layer 1: command check ---
    # Collect every missing command instead of stopping at the first one.
    for cmd in "${commands[@]}"; do
        if command -v "$cmd" > /dev/null 2>&1; then
            echo "$cmd: found"
        else
            echo "$cmd: missing"
            missing_commands+=("$cmd")
        fi
    done
    # "command -v "$cmd" > /dev/null 2>&1" runs at System Shell / OS Binaries
    # > /dev/null 2>&1  this won't print normal and error output

    # --- Layer 3: GTK 4 Python bindings check ---
    if command -v python3 >/dev/null 2>&1; then
        if python3 -c 'import gi; gi.require_version("Gtk", "4.0"); from gi.repository import Gtk' 2>/dev/null; then
            echo "GTK 4: found"
            # the above python3 command runs at Python Runtime Environment
            # 2>/dev/null   this won't print error output but normal output would still appear
        else
            echo "GTK 4: missing"
            missing_components+=("GTK-4 Python bindings")
        fi
    else
        echo "GTK 4: skipped (python3 is missing)"
    fi

    # --- Layer 4: library check ---
    # win2xcur depends on libmagickwand-dev, which is an APT package, not a command like python3, gsettings, etc.
    if dpkg -s libmagickwand-dev >/dev/null 2>&1; then
        echo "libmagickwand-dev: found"
        # dpkg -s displays information about an installed Debian package
    else
        echo "libmagickwand-dev: missing"
        missing_components+=("libmagickwand-dev")
    fi

    # --- Layer 5: report with install hints ---
    print_install() {
        local -A command_status=(
            [python3]=1
            [gsettings]=1
            [win2xcur]=1
            [pipx]=1
        )

        local -A component_status=(
            [GTK-4]=1
            [libmagickwand-dev]=1
        )

        for cmd in "${missing_commands[@]}"; do
            command_status["$cmd"]=0
        done

        for cmp in "${missing_components[@]}"; do
            case "$cmp" in
                "GTK-4 Python bindings")
                    component_status[GTK-4]=0
                    ;;
                "libmagickwand-dev")
                    component_status[libmagickwand-dev]=0
                    ;;
            esac
        done

        local apt_packages=()

        [[ "${command_status[python3]}" == 0 ]] && apt_packages+=(python3)
        [[ "${command_status[gsettings]}" == 0 ]] && apt_packages+=(libglib2.0-bin)
        [[ "${command_status[pipx]}" == 0 ]] && apt_packages+=(pipx)

        [[ "${component_status[GTK-4]}" == 0 ]] && apt_packages+=(python3-gi gir1.2-gtk-4.0)
        [[ "${component_status[libmagickwand-dev]}" == 0 ]] && apt_packages+=(libmagickwand-dev)

        if [[ ${#apt_packages[@]} -gt 0 ]]; then
            echo
            echo "Missing APT dependencies detected."
            echo "Try running the following commands:"
            echo
            echo "    sudo apt update"
            echo "    sudo apt install ${apt_packages[*]}"
        fi

        if [[ "${command_status[win2xcur]}" == 0 ]]; then
            echo
            echo "win2xcur is missing."
            echo "Try running:"
            echo
            echo "    pipx install win2xcur"
        fi
    }
    print_install

    # --- Layer 6: exit code ---
    local missing=$((${#missing_commands[@]} + ${#missing_components[@]}))
    if [ "$missing" -eq 0 ]; then
        echo "All dependencies are installed!"
        return 0
    else
        echo "$missing dependencies are missing."
        return 1
    fi
}

check_deps