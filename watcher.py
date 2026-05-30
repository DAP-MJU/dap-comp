import subprocess
import json
import os
import sys
import signal
import shutil
from dotenv import load_dotenv

load_dotenv()

GWS = shutil.which("gws.cmd") or shutil.which("gws") or "gws"

GCP_PROJECT = os.getenv("GCP_PROJECT", "dap-mju")
POLL_INTERVAL = int(os.getenv("WATCH_POLL_INTERVAL", "5"))
PIPELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pipeline.py")
PYTHON = sys.executable

_watcher_proc = None
_shutting_down = False


def handle_sigint(sig, frame):
    global _shutting_down

    if _shutting_down:
        return

    _shutting_down = True

    if _watcher_proc and _watcher_proc.poll() is None:
        _watcher_proc.terminate()

    sys.exit(0)


def should_process(email_json: dict) -> bool:
    labels = email_json.get("labelIds", [])

    return (
        "INBOX" in labels
        and "DRAFT" not in labels
        and "SENT" not in labels
    )


def process_email(email_id: str) -> None:
    print(f"\n⚡ 새 메일 처리 시작: {email_id}")

    result = subprocess.run(
        [
            PYTHON,
            PIPELINE,
            "--message-id",
            email_id
        ],
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False
    )

    if result.returncode != 0:
        print(f"   ⚠️  pipeline.py 종료 코드: {result.returncode}")


def main() -> None:
    global _watcher_proc

    signal.signal(signal.SIGINT, handle_sigint)

    print("👀 Gmail 새 메일 감지 시작")
    print(f"   GCP 프로젝트  : {GCP_PROJECT}")
    print(f"   라벨 필터     : INBOX (DRAFT, SENT 제외)")
    print(f"   폴링 간격     : {POLL_INTERVAL}초")
    print(f"   GWS 경로      : {GWS}")
    print("   Ctrl+C 로 종료\n")

    cmd = [
        GWS,
        "gmail",
        "+watch",
        "--project",
        GCP_PROJECT,
        "--label-ids",
        "INBOX",
        "--poll-interval",
        str(POLL_INTERVAL)
    ]

    _watcher_proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        shell=False
    )

    try:
        for raw_line in _watcher_proc.stdout:
            if _shutting_down:
                break

            line = raw_line.strip()

            if not line:
                continue

            try:
                email_json = json.loads(line)
            except json.JSONDecodeError:
                print(f"   ℹ️  {line}")
                continue

            email_id = email_json.get("id")

            if not email_id:
                continue

            labels = email_json.get("labelIds", [])

            if not should_process(email_json):
                print(f"   ⏭️  스킵 [{email_id}]  라벨: {labels}")
                continue

            process_email(email_id)

    except KeyboardInterrupt:
        pass

    finally:
        if _watcher_proc and _watcher_proc.poll() is None:
            _watcher_proc.terminate()

        print("\n👋 watcher 종료")


if __name__ == "__main__":
    main()