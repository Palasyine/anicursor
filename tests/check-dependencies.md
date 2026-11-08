All of these simulate a missing dependency by changing what the script can see, so nothing is uninstalled and your real files stay untouched. Run them from the project root.

1. Everything installed (baseline)
bash
PATH="$HOME/.local/bin:$PATH" bash scripts/check-dependencies.sh; echo "exit: $?"

Expected: no output, exit: 0. The PATH prefix is there because the PATH fix now lives in the launcher, not in this script.

2. Unknown / fake command
bash
sed 's/local commands=(python3 gsettings win2xcur)/local commands=(python3 gsettings win2xcur fakecmd)/' \
    scripts/check-dependencies.sh > /tmp/test-fake.sh
PATH="$HOME/.local/bin:$PATH" bash /tmp/test-fake.sh; echo "exit: $?"
rm /tmp/test-fake.sh

sed writes a modified copy to /tmp, so the real script isn’t edited. Expected: Warning: Unknown dependency 'fakecmd', then 1 dependencies are missing., exit: 1. If the sed pattern doesn’t match (nothing changes), check that the commands= line is spelled exactly the same in your file.

3. win2xcur missing (pipx still present)
bash
env PATH=/usr/bin:/bin bash scripts/check-dependencies.sh; echo "exit: $?"

win2xcur lives in ~/.local/bin, which isn’t in that PATH, so it looks missing. Expected: the pipx install win2xcur block, exit: 1. This is also the “running the script directly” limitation from your header comment, which is why the launcher must set PATH.

4. libmagickwand-dev missing
bash
( dpkg() { return 1; }; export -f dpkg
  PATH="$HOME/.local/bin:$PATH" bash scripts/check-dependencies.sh; echo "exit: $?" )

This defines a fake dpkg that always fails, exports it to the child script, and discards it when the parentheses close. Expected: an apt block listing libmagickwand-dev, with no stray dpkg message, exit: 1. Look up export -f and why a function takes priority over a command with the same name.

5. GTK 4 bindings missing
bash
( python3() { return 1; }; export -f python3
  PATH="$HOME/.local/bin:$PATH" bash scripts/check-dependencies.sh; echo "exit: $?" )

command -v python3 still finds the function, but the import test fails. Expected: an apt block with python3-gi gir1.2-gtk-4.0, exit: 1.

6. Several things missing at once
bash
( dpkg() { return 1; }; python3() { return 1; }; export -f dpkg python3
  env PATH=/usr/bin:/bin bash scripts/check-dependencies.sh; echo "exit: $?" )

Expected: one apt block containing the GTK packages and libmagickwand-dev, the pipx block, and 3 dependencies are missing. (win2xcur, gtk4, libmagickwand-dev). This checks that the "${missing[@]}" handoff passes every element.

7. pipx and win2xcur both missing
bash
d=$(mktemp -d)
for c in python3 gsettings dpkg; do ln -s "$(command -v "$c")" "$d/$c"; done
env PATH="$d" /usr/bin/bash scripts/check-dependencies.sh; echo "exit: $?"
rm -r "$d"

This builds a temporary bin folder containing only the commands you want visible, so pipx and win2xcur truly don’t exist. Bash is called by its full path because env would otherwise search the restricted PATH for it. Expected: pipx inside the apt line, then the pipx block with the ensurepath note, exit: 1.

8. Test print_install directly

bash
bash -c 'source scripts/check-dependencies.sh; print_install python3 gtk4 win2xcur'

Expected: the apt line with python3 python3-gi gir1.2-gtk-4.0 and the pipx block, and no system checks. Add an unknown name to see the warning:

bash
bash -c 'source scripts/check-dependencies.sh; print_install nonsense'
Debugging helpers

If a result surprises you, trace it:
git
bash
PATH="$HOME/.local/bin:$PATH" bash -x scripts/check-dependencies.sh

Finish with shellcheck scripts/check-dependencies.sh.