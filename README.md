# File Replicator

Replicate files one-way to another computer e.g. for remote development.

A key use-case is to keep in sync a directory of development files from a computer on which
the files are edited with a copy of those files in a docker container running on a remote docker host.

Dependencies are:
* Python and some Python packages on the development machine
* Ability to run bash on the remote machine with connected `stdin`

Nothing is installed remotely.

This has only been tested between two Linux machines.

# How it works

The approach is to run a small bash program on the remote end which is able to add/update new files in
(potentially) new directories. It receives instructions over `stdin`, endlessly waiting for:

* an absolute path to a filename
* a newline
* an integer number of bytes
* a newline
* that many bytes of data
* ...repeat...

The controlling end then simply sends files over to the `stdin` of the receiving bash program.
Establishing the connection to the remote end is outside the remit of this tool, but `file-replicator`
requires as an argument the command to make such a connection. See examples below.

Once a connection has been made, two operations occur:

1. recursively walk a source tree of files and sending all of them over the wire to the destination
2. watching for changes or new files and directories before sending them over the wire to the destination

So there is no "difference algorithm" like rsync, no attempt to compress, the connection is made
entirely using standard means like ssh and docker, no ports to open, and even the bash program
on the remote end is sent over every time so nothing is installed remotely.

This is sufficient for editing code on a local computer and automatically replicating to a remote server
or docker container.

# Usage and examples

See help with `file-replicate --help`:

    Usage: file-replicator [OPTIONS] SRC_DIR DEST_PARENT_DIR
                           [CONNECTION_COMMAND]...

      Replicate files to another computer e.g. for remote development.

      SRC_DIR is the source directory on this machine.

      DEST_PARENT_DIR is the (absolute) destination parent directory on the
      remote machine accessed using the CONNECTION_COMMAND.

      The CONNECTION_COMMAND must result in a running instance of bash ready to
      receive commands on stdin.

      Example CONNECTION_COMMANDS include:

          ssh some.host.com bash

          docker exec -i my_container bash

          docker-compose exec -T my_container bash

      So a full use of the tool might look like:

          file-replicator my_code_dir /home/code -- docker exec -i a_container bash

      (the use of "--" prevents any further processing of command line arguments
      by file-replicator, leaving them all for docker)

      Initially, all files and required directories are recursively copied. Then
      waits for changes before copying each modified or new file.

      Note that empty directories are not replicated until they contain a file.

      Lastly, the only time the tool deletes files or directories is if called
      with the optional --clean-out-first switch.

    Options:
      --clean-out-first  Optionally start by cleaning out the destination
                         directory.
      --help             Show this message and exit.


For example, to replicate files from local directory `my_project_dir` to directory
`/home/code/my_project_dir` on remote machine called `my.server.com`:

    file-replicator my_project_dir /home/code ssh my.server.com bash

As another example, to replicate files from local directory `my_project_dir` to directory
`/home/code/my_project_dir` in a running docker container called `my_container` on a potentially
remote host (depending upon the `DOCKER*` environment variables e.g. as set by `docker-machine eval`):

    file-replicator my_project_dir /home/code -- docker exec -i my_container bash

Or to do the same but using `docker-compose` instead:

    file-replicator my_project_dir /home/code -- docker-compose exec -T my_container bash

Lastly, as a degenerate example which doesn't actually connect to a remote machine at all
but replicates into the locall `/tmp/my_project_dir`:

    file-replicator my_project_dir /tmp bash

The unit tests use this degenerate approach to test the tool.

# Limitations

Due to limitations with inotify (race conditions around watching for changes in newly created directories), it
is possible that the watching-for-changes phase becomes out of step. In which case, just restart the whole program.
(the tool includes some self-restarting behaviour, but ultimately a full restart may sometimes be needed).

Information printed to stdout indicates when this happens.

# Tests

    ============================= test session starts ==============================
    platform linux -- Python 3.6.7, pytest-3.10.1, py-1.7.0, pluggy-0.8.0 -- /home/tcorbettclark/.cache/pypoetry/virtualenvs/file-replicator-py3.6/bin/python
    cachedir: .pytest_cache
    rootdir: /home/tcorbettclark/code/file-replicator, inifile:
    collecting ... collected 8 items

    tests/test_lib.py::test_empty_directories_are_not_copied PASSED            [ 12%]
    tests/test_lib.py::test_copy_one_file PASSED                               [ 25%]
    tests/test_lib.py::test_copy_file_with_unusual_characters_in_name PASSED   [ 37%]
    tests/test_lib.py::test_make_missing_parent_directories PASSED             [ 50%]
    tests/test_lib.py::test_replicate_all_files PASSED                         [ 62%]
    tests/test_lib.py::test_detect_and_copy_new_file PASSED                    [ 75%]
    tests/test_lib.py::test_detect_and_copy_modified_file PASSED               [ 87%]
    tests/test_lib.py::test_detect_and_copy_new_file_in_new_directories PASSED [100%]

    =========================== 8 passed in 3.93 seconds ===========================

# Contributions

Pull-requests are welcome! Please consider including tests and updating docs at the same time.

The package is maintained using poetry (https://poetry.eustace.io) and pyenv (https://github.com/pyenv/pyenv).

The code is formatted using black (https://black.readthedocs.io/en/stable) and isort (https://github.com/timothycrosley/isort).

It is tested using pytest (https://pytest.org).

# Commit checklist

1. check version both in `pyproject.toml` and `file_replicator/__init__.py`
1. `git tag`
1. `isort -rc .`
1. `black .`
1. `pytest -v`
1. update this README.md with the latest output from the tests
1. update this README.md with the latest output from the --help option
