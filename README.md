# File Replicator

Replicate files one-way to another computer e.g. for remote development.

A key use-case is to keep in sync a directory of development files from a computer on which
the files are edited with a copy of those files in a docker container running on a remote docker host.

Dependencies are:
* Python and some Python packages on the development machine
* Ability to run bash (including busybox) on the remote machine with connected `stdin`

Nothing is installed remotely.

This has only been tested between two Linux machines.

# How it works

The approach is to run a small bash program on the remote end which is able to add/update new files in
(potentially) new directories. It receives commands over `stdin`, endlessly waiting for:
* an absolute path to a filename
* a newline
* an integer number of bytes
* a newline
* that many bytes of data
* ...repeat...

The controlling end then simply sends files over to the `stdin` of the receiving bash program.
Establishing the connection to the remote end is outside the remit of this tool. Instead it accepts
as an argument the command to make such a connection. See examples below.

It has two key operations:

1. recursively walking a source tree of files and sending them over the wire to the destination
2. watching for changes or new files and directories before sending them over the wire to the destination

So there is no "difference algorithm" like rsync, no attempt to compress, the connection is made
entirely using standard means like ssh and docker, no ports to open, and even the bash program
on the remote end is sent over every time so nothing is installed remotely.

This is sufficient for editing code on a local computer and automatically replicating to a remote server
or docker container.

# Usage and examples

See help:

    TODO update help

Replicate files from local directory `my_project` to directory `/home/code/my_project` on
remote machine called `my.server.com`:

    file-replicator my_project /home/code ssh my.server.com bash

To replicate files from local directory `my_project` to directory `/home/code/my_project` in a
running docker container called `my_container` on a potentially remote host (depending upon the `DOCKER*`
environment variables e.g. as set by `docker-machine eval`):

    file-replicator my_project /home/code -- docker exec -i my_container bash

Or to do the same but using `docker-compose` instead:

    file-replicator my_project /home/code -- docker-compose exec -T my_container bash

# Limitations

Due to limitations with inotify (race conditions around watching for changes in newly created directories), it
is possible that the watching-for-changes phase becomes out of step. In which case, just restart the whole program.
(the tool includes some self-restarting behaviour, but ultimately a full restart may sometimes be needed).

Information printed to stdout indicates when this happens.

# Tests

TODO copy and paste

# Contributions

Pull-requests welcome. Please considering including tests.

The package is maintained using poetry (https://poetry.eustace.io) and pyenv (https://github.com/pyenv/pyenv).

The code is formatted using black (https://black.readthedocs.io/en/stable).

It is tested using pytest (`poetry run pytest`). Note that in order to run these tests the current user
must be able to ssh to localhost without a password.

# Commit checklist

1. check version both in `pyproject.toml` and `file_replicator/__init__.py`
1. isort -rc .
1. black .
1. pytest -v
1. update this README.md with the latest output from the tests
1. update this README.md with the latest output from the --help option

# TODO

Add option to exclude certain files
Add docs to show an example output. Possibly a screenshot so it looks nice.
Publish on Pypi. (check copyright etc)