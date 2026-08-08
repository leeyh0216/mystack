"""Drop the trusted container entrypoint from root to hadoop, then replace PID 1.

Python process identity and exec references:
https://docs.python.org/3.11/library/os.html#os.setuid
https://docs.python.org/3.11/library/os.html#os.execvpe
"""

from __future__ import annotations

import json
import os
import pwd
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import NoReturn


class HadoopPrivilegeDropper:
    """Fixed-identity adapter used only after reviewed root initialization completes."""

    def __init__(self, user: str = "hadoop") -> None:
        self._user = user

    def exec(self, command: Sequence[str]) -> NoReturn:
        if not command:
            self._fail("No service command was supplied")
        if os.getuid() != 0:
            self._fail("Privilege drop must begin as root")
        try:
            identity = pwd.getpwnam(self._user)
        except KeyError:
            self._fail("The fixed service identity does not exist")
        try:
            os.initgroups(identity.pw_name, identity.pw_gid)
            os.setgid(identity.pw_gid)
            os.setuid(identity.pw_uid)
        except OSError as error:
            self._fail(f"Could not select the fixed service identity: {type(error).__name__}")
        if os.getuid() != identity.pw_uid or os.getgid() != identity.pw_gid:
            self._fail("Kernel identity does not match the fixed service identity")
        self._log(
            {
                "event": "emr.entrypoint.privilege_drop.after",
                "gid": identity.pw_gid,
                "level": "INFO",
                "service": "emr-entrypoint",
                "side_effect": True,
                "target_user": identity.pw_name,
                "uid": identity.pw_uid,
            }
        )
        try:
            os.execvpe(command[0], list(command), os.environ)
        except OSError as error:
            self._fail(f"Could not exec the service command: {type(error).__name__}")

    @staticmethod
    def _fail(reason: str) -> NoReturn:
        HadoopPrivilegeDropper._log(
            {
                "event": "emr.entrypoint.privilege_drop.failed",
                "level": "ERROR",
                "reason": reason,
                "fix_hint": (
                    "Keep the image entrypoint root-owned and verify the fixed hadoop account "
                    "and service command; arguments and environment values were not logged."
                ),
                "service": "emr-entrypoint",
            }
        )
        raise SystemExit(126)

    @staticmethod
    def _log(fields: dict[str, object]) -> None:
        print(
            json.dumps(
                {"timestamp": datetime.now(UTC).isoformat(), **fields},
                sort_keys=True,
            ),
            file=sys.stderr,
            flush=True,
        )


def run() -> NoReturn:
    HadoopPrivilegeDropper().exec(sys.argv[1:])
