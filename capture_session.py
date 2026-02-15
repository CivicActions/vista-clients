#!/usr/bin/env python3
"""Capture VistA VEHU SSH terminal session with raw output."""
import subprocess
import time
import sys
import os
import select
import fcntl

def set_nonblocking(fd):
    fl = fcntl.fcntl(fd, fcntl.F_GETFL)
    fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

def read_available(fd, timeout=3.0):
    """Read all available data from fd within timeout."""
    data = b""
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.2)
        if ready:
            try:
                chunk = os.read(fd.fileno(), 65536)
                if not chunk:
                    break
                data += chunk
            except (BlockingIOError, OSError):
                break
    return data

def main():
    print("=" * 60)
    print("VistA VEHU SSH Session Capture")
    print("=" * 60)

    # Use sshpass if available, otherwise raw ssh
    proc = subprocess.Popen(
        ['sshpass', '-p', 'tied', 'ssh', '-o', 'StrictHostKeyChecking=no',
         '-o', 'UserKnownHostsFile=/dev/null', '-p', '2222', '-tt', 'vehutied@localhost'],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    set_nonblocking(proc.stdout)
    set_nonblocking(proc.stderr)

    all_output = b""

    def capture_and_print(label, timeout=5.0):
        nonlocal all_output
        data = read_available(proc.stdout, timeout)
        stderr_data = read_available(proc.stderr, 0.5)
        if data:
            all_output += data
            print(f"\n{'='*60}")
            print(f"PHASE: {label}")
            print(f"{'='*60}")
            print(f"RAW (repr): {repr(data)}")
            print(f"DECODED (utf-8):\n{data.decode('utf-8', errors='replace')}")
        if stderr_data:
            print(f"STDERR: {repr(stderr_data)}")
        return data

    # Phase 1: SSH connection + password
    print("\n>>> Phase 1: SSH Connection")
    capture_and_print("SSH_CONNECT", timeout=8.0)

    # Phase 2: Wait for VistA banner + ACCESS CODE prompt
    print("\n>>> Phase 2: Wait for ACCESS CODE")
    capture_and_print("VISTA_BANNER", timeout=10.0)

    # Phase 3: Send ACCESS CODE
    print("\n>>> Phase 3: Sending ACCESS CODE: facprov1")
    proc.stdin.write(b"facprov1\r")
    proc.stdin.flush()
    time.sleep(2)
    capture_and_print("AFTER_ACCESS_CODE", timeout=5.0)

    # Phase 4: Send VERIFY CODE
    print("\n>>> Phase 4: Sending VERIFY CODE")
    proc.stdin.write(b"1Prov!@#$\r")
    proc.stdin.flush()
    time.sleep(3)
    capture_and_print("AFTER_VERIFY_CODE", timeout=10.0)

    # Phase 5: Handle post-login prompts (device selection, etc.)
    print("\n>>> Phase 5: Post-login prompts")
    time.sleep(2)
    capture_and_print("POST_LOGIN_1", timeout=8.0)

    # Send empty line to handle any intermediate prompt
    proc.stdin.write(b"\r")
    proc.stdin.flush()
    time.sleep(2)
    capture_and_print("POST_LOGIN_2", timeout=5.0)

    # Send another empty line
    proc.stdin.write(b"\r")
    proc.stdin.flush()
    time.sleep(2)
    capture_and_print("POST_LOGIN_3", timeout=5.0)

    # Send another empty line
    proc.stdin.write(b"\r")
    proc.stdin.flush()
    time.sleep(2)
    capture_and_print("POST_LOGIN_4", timeout=5.0)

    # Send another empty line
    proc.stdin.write(b"\r")
    proc.stdin.flush()
    time.sleep(2)
    capture_and_print("POST_LOGIN_5", timeout=5.0)

    # Phase 6: Try to halt
    print("\n>>> Phase 6: Sending HALT")
    proc.stdin.write(b"^\r")
    proc.stdin.flush()
    time.sleep(2)
    capture_and_print("HALT", timeout=5.0)

    proc.kill()
    proc.wait()

    print("\n" + "=" * 60)
    print("COMPLETE RAW SESSION OUTPUT (repr)")
    print("=" * 60)
    print(repr(all_output))

    print("\n" + "=" * 60)
    print("COMPLETE SESSION OUTPUT (decoded)")
    print("=" * 60)
    print(all_output.decode('utf-8', errors='replace'))

if __name__ == "__main__":
    main()
