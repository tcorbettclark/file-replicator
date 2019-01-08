import contextlib
import os.path
import shutil
import subprocess
import time

import inotify.adapters

__all__ = ["make_file_replicator", "replicate_all_files", "replicate_files_on_change"]


# Small receiver code (written in bash for minimum dependencies) which reads a
# filename from the first line, a size from the second line, and then copies that many
# bytes into the given filename, creating any parent directories if necessary.
# Then repeat forever until no filename is given.
RECEIVER_CODE = """
set -e
while true; do
    read filename
    read size
    [ -z "$filename" ] && break
    mkdir -p "$(dirname "$filename")"
    echo -n "Writing file $filename ($size bytes)..."

    if [ $size = 0 ]; then
        # dd will not fetch zero bytes so handle this as a special case.
        touch "$filename"
    else
        # Try to fetch it all in one go...
        dd bs=$size count=1 of="$filename" status=none

        # ... but we may not have it all due to non-blocking and buffering etc. So keep trying.
        current_size=$(stat -c "%s" "$filename")
        while [ $current_size != $size ]; do
            dd bs=$(( $size - $current_size )) count=1 status=none >>"$filename"
            current_size=$(stat -c "%s" "$filename")
        done
    fi
    echo Done
done
"""


@contextlib.contextmanager
def make_file_replicator(
    src_dir, dest_parent_dir, bash_connection_command, clean_out_first=False
):
    """Yield a copy_file(<filename>) function for replicating files over a "bash connection".

    The <filename> must be in the given <src_dir>. The final path in the <src_dir>
    becomes the destination directory in the <dest_parent_dir>.

    The <bash_connection_command> must be a list.

    """
    src_dir = os.path.abspath(src_dir)
    dest_parent_dir = os.path.abspath(dest_parent_dir)
    destination_dir = os.path.join(dest_parent_dir, os.path.basename(src_dir))

    p = subprocess.Popen(bash_connection_command, stdin=subprocess.PIPE)

    # Get the remote end up and running, waiting for commands.
    if clean_out_first:
        # Only delete the *contents* of the destination directory so that the
        # inode does not change (because that is irritating!).
        p.stdin.write(f"rm -rf {destination_dir}/*\n".encode())
    p.stdin.write(RECEIVER_CODE.encode())
    p.stdin.flush()

    def copy_file(src_filename):
        src_filename = os.path.abspath(src_filename)
        assert src_filename.startswith(src_dir), src_filename
        assert os.path.isfile(src_filename)
        size = os.path.getsize(src_filename)
        dest_filename = os.path.join(
            destination_dir, src_filename[(1 + len(src_dir)) :]
        )
        p.stdin.write(f"{dest_filename}\n".encode())
        p.stdin.write(f"{size}\n".encode())
        with open(src_filename, "rb") as f:
            shutil.copyfileobj(f, p.stdin)
        p.stdin.flush()

    try:
        yield copy_file
    finally:
        p.stdin.close()
        p.wait()


def replicate_all_files(src_dir, copy_file):
    """Walk src_dir to copy all files using copy_file()."""
    for root, dirnames, filenames in os.walk(src_dir):
        for filename in filenames:
            copy_file(os.path.join(root, filename))


def replicate_files_on_change(src_dir, copy_file, timeout=None):
    """Wait for changes to files in src_dir and copy with copy_file().

    If provided, the timeout indicates when to return after that many seconds of no change.

    This is an imperfect solution because there are seemingly unavoidable race conditions
    when watching for file changes or additions and new directories are involved.

    Returns True to indicate that new directories have been added and the function should
    be called again. Otherwise returns None.

    """
    please_call_me_again = False
    i = inotify.adapters.InotifyTree(src_dir)
    for event in i.event_gen(yield_nones=False, timeout_s=timeout):
        (_, type_names, path, filename) = event
        # For debugging...
        # print(
        #     "PATH=[{}] FILENAME=[{}] EVENT_TYPES={}".format(path, filename, type_names)
        # )
        if "IN_CLOSE_WRITE" in type_names:
            copy_file(os.path.join(path, filename))
        if "IN_CREATE" in type_names and "IN_ISDIR" in type_names:
            # Race condition danger because a new directory was created (see warning on https://pypi.org/project/inotify).
            # Wait a short while for things to settle, then replicate the new directory, then start the watchers again.
            time.sleep(0.5)
            new_directory = os.path.join(path, filename)
            replicate_all_files(new_directory, copy_file)
            please_call_me_again = True
            break
    return please_call_me_again
