#!/bin/sh
# Compile the locales the desktop needs into $1/usr/lib/locale (directory
# form, no locale-archive). glibc's C.UTF-8 is not built in: without a
# compiled C.utf8 every program run with LANG=C.UTF-8 (the GDM/GNOME
# default here) gets "Locale not supported by C library", and
# gnome-terminal-server refuses to start at all.
set -e
dest="$1/usr/lib/locale"
mkdir -p "$dest"
for spec in C.UTF-8 en_US.UTF-8; do
  name=${spec%.*}
  charset=${spec#*.}
  localedef -i "$name" -f "$charset" --no-archive "$dest/$name.utf8"
done
