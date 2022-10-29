#!/bin/sh
# Migration script
[ ! -d "$1" ] && exit 1
[ ! -f "$1/run" ] && exit 1
. "$1/run"
NYAA_REPO_BIN="$HOME/projects/src/nyaa-repo-bin/$1-bin"
mkdir -p "$NYAA_REPO_BIN"
echo "#!/bin/sh" > "$NYAA_REPO_BIN/run"
echo "NAME='$NAME'" >> "$NYAA_REPO_BIN/run"
echo "VERSION='$VERSION'" >> "$NYAA_REPO_BIN/run"
echo "IS_BINARY='y'" >> "$NYAA_REPO_BIN/run"
[ -f "$1/deps" ] && cp "$1/deps" "$NYAA_REPO_BIN/deps"
if [ -f "$1/build_deps" ]
then
    for i in "$(cat $1/build_deps)"
    do
        echo "adding $i to $1/deps"
        echo "$i" >> "$1/deps"
    done
    rm -f "$1/build_deps"
fi
