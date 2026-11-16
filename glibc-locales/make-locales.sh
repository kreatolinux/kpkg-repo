#!/bin/sh
# Compile C.UTF-8 and en_US.UTF-8 into $1/usr/lib/locale. glibc has no built-in
# C.UTF-8 and gnome-terminal-server refuses to start without it; en_US.UTF-8 is
# the desktop's other locale.
set -e
dest="$1/usr/lib/locale"
mkdir -p "$dest"
for spec in C.UTF-8 en_US.UTF-8; do
  name=${spec%.*}
  charset=${spec#*.}
  localedef -i "$name" -f "$charset" --no-archive "$dest/$name.utf8"
done
