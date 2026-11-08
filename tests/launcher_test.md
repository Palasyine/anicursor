Scenario	Command	Expected
All present	bin/anicursor; echo "exit: $?"	anicursor starting [], exit: 0
Arguments forwarded	bin/anicursor --test	anicursor starting ['--test']
From another folder	cd ~ && ~/Documents/Side_Project/anicursor/bin/anicursor	Same output
Through a symlink	ln -s "$PWD/bin/anicursor" /tmp/anicursor-link && /tmp/anicursor-link; rm /tmp/anicursor-link	Same output
Dependency missing, terminal	( dpkg() { return 1; }; export -f dpkg; bin/anicursor; echo "exit: $?" )	Report printed, exit: 1, no “starting”
Dependency missing, dialog	( dpkg() { return 1; }; export -f dpkg; bin/anicursor 2>/dev/null; echo "exit: $?" )	A zenity dialog
No zenity	d=$(mktemp -d); env PATH="$d" /usr/bin/bash -c 'source bin/anicursor; notify_error "Test message"' 2>/tmp/err.txt; cat /tmp/err.txt; rm -r "$d" /tmp/err.txt	Test message in the file
No graphical session	env -u WAYLAND_DISPLAY -u DISPLAY bin/anicursor 2>/tmp/err.txt with the fake dpkg, then cat /tmp/err.txt	The report in the file, no dialog
