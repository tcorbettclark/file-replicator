import os.path

import click

from .lib import make_file_replicator, replicate_all_files, replicate_files_on_change


@click.command()
@click.argument("src_dir")
@click.argument("dest_parent_dir")
@click.argument("connection_command", nargs=-1)
@click.option(
    "--clean-out-first",
    is_flag=True,
    default=False,
    help="Optionally start by cleaning out the destination directory.",
)
def main(src_dir, dest_parent_dir, connection_command, clean_out_first):
    """Replicate files to another computer e.g. for remote development.

    SRC_DIR is the source directory on this machine.

    DEST_PARENT_DIR is the (absolute) destination parent directory on the
    remote machine accessed using the CONNECTION_COMMAND.

    The CONNECTION_COMMAND must result in a running instance of bash ready to receive commands
    on stdin.

    Example CONNECTION_COMMANDS include:

        ssh some.host.com bash

        docker exec -i my_container bash

        docker-compose exec -T my_container bash

    So a full use of the tool might look like:

        file-replicator my_code_dir /home/code -- docker exec -i a_container bash

    (the use of "--" prevents any further processing of command line arguments by
    file-replicator, leaving them all for docker)

    Initially, all files and required directories are recursively copied. Then it
    waits for changes before copying each modified or new file.

    Note that empty directories are not replicated until they contain a file.

    Lastly, the only time the tool deletes files or directories is if called with
    the optional --clean-out-first switch.

    """
    if not connection_command:
        raise click.UsageError(
            "Please provide a connection command to access the destination server."
        )
    if not os.path.isabs(dest_parent_dir):
        raise click.UsageError(
            "The destination parent directory must be an absolute path."
        )
    if not os.path.exists(src_dir) or not os.path.isdir(src_dir):
        raise click.UsageError("The source destination must exist and be a directory.")

    if clean_out_first:
        click.secho(
            "Clearing out all destination files first!", fg="green", bold="true"
        )

    with make_file_replicator(
        src_dir, dest_parent_dir, connection_command, clean_out_first=clean_out_first
    ) as copy_file:
        replicate_all_files(src_dir, copy_file)
        while replicate_files_on_change(src_dir, copy_file):
            click.secho(
                "Restarting watchers after detecting a new directory. Consider restarting!",
                fg="red",
                bold="true",
            )
