#!/bin/sh
# Non-systemd replacement for gnome-session-init-worker.
#
# Upstream gnome-session factors init-system-specific startup into this helper
# precisely so GNOME can be integrated with inits other than systemd
# (see leader-main.c). The stock helper starts gnome-session@<session>.target
# through org.freedesktop.systemd1 and calls g_error() -- which aborts -- when
# that name is not on the bus.
#
# The jumpstart systemd core does not expose systemd's D-Bus manager API, so
# this shim starts the session manager directly and then signals the
# "initialized" transition over D-Bus. gnome-session exposes
# org.gnome.SessionManager.Initialized() for exactly this purpose: its own
# comment says "Signaled by helper when gnome-session-initialized.target is
# reached", and the handler advances the manager out of the INITIALIZATION
# phase and calls start_phase().

session_name="$1"
if [ -z "$session_name" ]; then
    echo "gnome-session-init-worker: no session name specified" >&2
    exit 1
fi

runtime_dir="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
fifo="$runtime_dir/gnome-session-leader-fifo"

if [ -d "$runtime_dir" ]; then
    if [ ! -p "$fifo" ]; then
        mkfifo "$fifo" 2>/dev/null
    fi
    if [ -p "$fifo" ]; then
        # O_RDWR on a FIFO never blocks, unlike O_WRONLY with no reader.
        exec 9<>"$fifo" 2>/dev/null
    fi
fi

# Start the session manager in the background so we can drive its phase
# transitions. It owns the session bus connection we inherit.
/usr/libexec/gnome-session-service --session="$session_name" &
session_pid=$!

# Wait for org.gnome.SessionManager to appear on the session bus, then call
# Initialized() to advance past the INITIALIZATION phase. Poll for up to 30s:
# a user session has more to set up than the greeter and can be slower.
i=0
while [ $i -lt 300 ]; do
    if gdbus introspect --session \
            --dest org.gnome.SessionManager \
            --object-path /org/gnome/SessionManager >/dev/null 2>&1; then
        break
    fi
    i=$((i + 1))
    sleep 0.1
done

gdbus call --session \
    --dest org.gnome.SessionManager \
    --object-path /org/gnome/SessionManager \
    --method org.gnome.SessionManager.Initialized >/dev/null 2>&1

wait "$session_pid"
