import contextlib
import os.path
import shutil
import subprocess
import time

import inotify.adapters
import pathspec

__all__ = ["make_file_replicator", "replicate_all_files", "replicate_files_on_change"]


# Small receiver code (written in bash for minimum dependencies) which repeatadly reads
# tar files from stdin and extracts them.
# Note that this requires the full tar command, not the busybox "lightweight" version.
RECEIVER_CODE = """
set -e
if {clean_out_first}; then
    rm -rf {dest_dir}/*
fi
mkdir -p {dest_dir}
cd {dest_dir}
while true; do
    tar --no-same-owner --extract --verbose
done
"""


@contextlib.contextmanager
def make_file_replicator(
    src_dir,
    dest_parent_dir,
    bash_connection_command,
    clean_out_first=False,
    debugging=False,
):
    """Yield a copy_file(<filename>) function for replicating files over a "bash connection".

    The <filename> must be in the given <src_dir>. The final path in the <src_dir>
    becomes the destination directory in the <dest_parent_dir>.

    The <bash_connection_command> must be a list.

    """
    src_dir = os.path.abspath(src_dir)
    dest_parent_dir = os.path.abspath(dest_parent_dir)
    dest_dir = os.path.join(dest_parent_dir, os.path.basename(src_dir))

    p = subprocess.Popen(bash_connection_command, stdin=subprocess.PIPE)

    # Get the remote end up and running waiting for tar files.
    receiver_code = RECEIVER_CODE.format(
        dest_dir=dest_dir, clean_out_first=str(clean_out_first).lower()
    )
    p.stdin.write(receiver_code.encode())
    p.stdin.flush()

    def copy_file(src_filename):
        src_filename = os.path.abspath(src_filename)
        rel_src_filename = os.path.relpath(src_filename, src_dir)
        if debugging:
            print(f"Sending {src_filename}...")
        result = subprocess.run(
            [
                "tar",
                "--create",
                rel_src_filename,
                "--to-stdout",
                "--ignore-failed-read",
            ],
            cwd=src_dir,
            check=True,
            stdout=p.stdin,
            stderr=subprocess.PIPE,
        )
        if result.stderr:
            if "No such file or directory" in result.stderr.decode():
                # Ignore because file was removed before we had a chance to copy it.
                pass
            else:
                raise RuntimeError(f"ERROR: {result.stderr.decode()}")
        p.stdin.flush()

    try:
        yield copy_file
    finally:
        p.stdin.close()
        p.wait()


def get_pathspec(src_dir, use_gitignore=True):
    gitignore_filename = os.path.join(src_dir, ".gitignore")
    if use_gitignore and os.path.isfile(gitignore_filename):
        with open(gitignore_filename) as f:
            spec = pathspec.PathSpec.from_lines("gitwildmatch", f)
    else:
        spec = pathspec.PathSpec.from_lines("gitwildmatch", [])
    return spec


def replicate_all_files(src_dir, copy_file, use_gitignore=True, debugging=False):
    """Walk src_dir to copy all files using copy_file()."""
    spec = get_pathspec(src_dir, use_gitignore)
    for filename in pathspec.util.iter_tree(src_dir):
        if not spec.match_file(filename):
            copy_file(os.path.join(src_dir, filename))


def replicate_files_on_change(
    src_dir, copy_file, timeout=None, use_gitignore=True, debugging=False
):
    """Wait for changes to files in src_dir and copy with copy_file().

    If provided, the timeout indicates when to return after that many seconds of no change.

    This is an imperfect solution because there are seemingly unavoidable race conditions
    when watching for file changes or additions and new directories are involved.

    Returns True to indicate that new directories have been added and the function should
    be called again. Otherwise returns False.

    """
    please_call_me_again = False
    i = inotify.adapters.InotifyTree(src_dir)
    spec = get_pathspec(src_dir, use_gitignore)
    for event in i.event_gen(yield_nones=False, timeout_s=timeout):
        (_, type_names, path, filename) = event
        full_path = os.path.abspath(os.path.join(path, filename))
        rel_to_src_dir_path = os.path.relpath(full_path, src_dir)
        if debugging:
            print(f"Detected change: {full_path} {type_names}")
        if not spec.match_file(rel_to_src_dir_path):
            if "IN_CREATE" in type_names and "IN_ISDIR" in type_names:
                # Race condition danger because a new directory was created (see warning on https://pypi.org/project/inotify).
                # Wait a short while for things to settle, then replicate the new directory, then start the watchers again.
                time.sleep(0.5)
                replicate_all_files(full_path, copy_file)
                please_call_me_again = True
                break
            elif "IN_CLOSE_WRITE" in type_names:
                copy_file(full_path)
    return please_call_me_again
