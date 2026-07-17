from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("packet", nargs="?")
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--sleep", type=float, default=0)
    parser.add_argument("--spawn-child", action="store_true")
    parser.add_argument("--ignore-sigterm", action="store_true")
    args = parser.parse_args()

    if args.ignore_sigterm:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

    child: subprocess.Popen[str] | None = None
    print(f"agent_pid={os.getpid()}", flush=True)
    if args.spawn_child:
        child = subprocess.Popen(  # nosec B603
            [
                sys.executable,
                "-c",
                "import os, time; print(f'child_ready={os.getpid()}', flush=True); time.sleep(120)",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if child.stdout is not None:
            print(child.stdout.readline().strip().replace("child_ready", "child_pid"), flush=True)

    if args.sleep:
        time.sleep(args.sleep)
    if child is not None and child.poll() is None:
        child.terminate()
    return args.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
