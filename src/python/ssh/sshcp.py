# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
import shlex
import subprocess
import time

import pexpect

# my libs
from common import AppError


class SshcpError(AppError):
    """
    Custom exception that describes the failure of the ssh command
    """

    pass


class Sshcp:
    """
    Scp command utility
    """

    __TIMEOUT_SECS = 180

    def __init__(self, host: str, port: int, user: str | None = None, password: str | None = None):
        if host is None:
            raise ValueError("Hostname not specified.")
        self.__host = host
        self.__port = port
        self.__user = user
        self.__password = password
        self.logger = logging.getLogger(self.__class__.__name__)

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild(self.__class__.__name__)

    def __run_command(self, command: str, flags: str, args: str) -> bytes:
        command_args = [command, flags]

        # Common flags
        command_args += [
            "-o",
            "StrictHostKeyChecking=no",  # ignore host key changes
            "-o",
            "UserKnownHostsFile=/dev/null",  # ignore known hosts file
            "-o",
            "LogLevel=error",  # suppress warnings
        ]

        if self.__password is None:
            command_args += [
                "-o",
                "PasswordAuthentication=no",  # don't ask for password
            ]
        else:
            command_args += [
                "-o",
                "PubkeyAuthentication=no",  # don't use key authentication
            ]

        command_args.append(args)

        command = " ".join(command_args)
        self.logger.debug("Command: {}".format(command))

        start_time = time.time()
        sp = pexpect.spawn(command)
        try:
            if self.__password is not None:
                i = sp.expect(
                    [
                        "password: ",  # i=0, all's good
                        pexpect.EOF,  # i=1, unknown error
                        "lost connection",  # i=2, connection refused
                        "Could not resolve hostname",  # i=3, bad hostname
                        "Connection refused",  # i=4, connection refused
                    ]
                )
                if i > 0:
                    before = sp.before.decode().strip() if sp.before != pexpect.EOF else ""
                    after = sp.after.decode().strip() if sp.after != pexpect.EOF else ""
                    self.logger.warning("Command failed: '{} - {}'".format(before, after))
                if i == 1:
                    error_msg = "Unknown error"
                    if sp.before.decode().strip():
                        error_msg += " - " + sp.before.decode().strip()
                    raise SshcpError(error_msg)
                elif i == 3:
                    raise SshcpError("Bad hostname: {}".format(self.__host))
                elif i in {2, 4}:
                    error_msg = "Connection refused by server"
                    if sp.before.decode().strip():
                        error_msg += " - " + sp.before.decode().strip()
                    raise SshcpError(error_msg)
                sp.sendline(self.__password)

            i = sp.expect(
                [
                    pexpect.EOF,  # i=0, all's good
                    "password: ",  # i=1, wrong password
                    "lost connection",  # i=2, connection refused
                    "Could not resolve hostname",  # i=3, bad hostname
                    "Connection refused",  # i=4, connection refused
                ],
                timeout=self.__TIMEOUT_SECS,
            )
            if i > 0:
                before = sp.before.decode().strip() if sp.before != pexpect.EOF else ""
                after = sp.after.decode().strip() if sp.after != pexpect.EOF else ""
                self.logger.warning("Command failed: '{} - {}'".format(before, after))
            if i == 1:
                raise SshcpError("Incorrect password")
            elif i == 3:
                raise SshcpError("Bad hostname: {}".format(self.__host))
            elif i in {2, 4}:
                error_msg = "Connection refused by server"
                if sp.before.decode().strip():
                    error_msg += " - " + sp.before.decode().strip()
                raise SshcpError(error_msg)

        except pexpect.exceptions.TIMEOUT as e:
            self.logger.exception("Timed out")
            self.logger.error("Command output before:\n{}".format(sp.before))
            raise SshcpError("Timed out") from e
        sp.close()
        end_time = time.time()

        self.logger.debug("Return code: {}".format(sp.exitstatus))
        self.logger.debug("Command took {:.3f}s".format(end_time - start_time))
        if sp.exitstatus != 0:
            before = sp.before.decode().strip() if sp.before != pexpect.EOF else ""
            after = sp.after.decode().strip() if sp.after != pexpect.EOF else ""
            self.logger.warning("Command failed: '{} - {}'".format(before, after))
            raise SshcpError(sp.before.decode().strip())

        return sp.before.replace(b"\r\n", b"\n").strip()

    def shell(self, command: str) -> bytes:
        """
        Run a shell command on the remote server and return stdout.

        Security: uses subprocess with an explicit argument list so the command
        string is passed to the remote shell as a single argument, preventing
        local shell injection. The remote shell still interprets the command,
        so callers must ensure paths are properly quoted (use shlex.quote).
        :param command:
        :return:
        """
        if not command:
            raise ValueError("Command cannot be empty")

        # Build SSH argument list — no shell=True, no string concatenation.
        # The command is passed as a single positional argument to ssh,
        # which forwards it verbatim to the remote shell.
        ssh_args = [
            "ssh",
            "-p", str(self.__port),
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=error",
        ]

        if self.__password is None:
            ssh_args += ["-o", "PasswordAuthentication=no"]
        else:
            ssh_args += ["-o", "PubkeyAuthentication=no"]

        ssh_args += ["{}@{}".format(self.__user, self.__host), command]

        self.logger.debug("shell args: {}".format(ssh_args))

        if self.__password is not None:
            # Still need pexpect to handle password prompt interactively
            flags = ["-p", str(self.__port)]
            args = ["{}@{}".format(self.__user, self.__host), command]
            return self.__run_command(command="ssh", flags=" ".join(flags), args=" ".join(args))

        # Key-based auth: use subprocess directly (no shell, safe arg passing)
        import time as _time
        start = _time.time()
        try:
            result = subprocess.run(
                ssh_args,
                capture_output=True,
                timeout=self.__TIMEOUT_SECS,
            )
        except subprocess.TimeoutExpired as e:
            raise SshcpError("Timed out") from e
        except Exception as e:
            raise SshcpError(str(e)) from e

        elapsed = _time.time() - start
        self.logger.debug("Return code: {}".format(result.returncode))
        self.logger.debug("Command took {:.3f}s".format(elapsed))

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", "replace").strip()
            self.logger.warning("shell failed: {}".format(stderr))
            raise SshcpError(stderr or "SSH command failed with code {}".format(result.returncode))

        return result.stdout.replace(b"\r\n", b"\n").strip()

    def copy(self, local_path: str, remote_path: str):
        """
        Copies local file at local_path to remote remote_path
        :param local_path:
        :param remote_path:
        :return:
        """
        if not local_path:
            raise ValueError("Local path cannot be empty")
        if not remote_path:
            raise ValueError("Remote path cannot be empty")

        flags = [
            "-q",  # quiet
            "-P",
            str(self.__port),  # port
        ]
        args = [local_path, "{}@{}:{}".format(self.__user, self.__host, remote_path)]
        self.__run_command(command="scp", flags=" ".join(flags), args=" ".join(args))
