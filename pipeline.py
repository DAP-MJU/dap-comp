import argparse
import subprocess
import json
import os
import shutil
import sys
import platform
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
GWS = shutil.which("gws.cmd") or shutil.which("gws") or "gws"

def _insert_subcmd():
    return "+insert" if platform.system() == "Windows" else "insert"

def parse_gws_output(stdout: str):
    idx = -1
    for i, ch in enumerate(stdout):
        if ch in ("{", "["):
            idx = i
            break
    if idx == -1:
        raise ValueError(f"JSON을 찾을 수 없음: {stdout[:200]}")
    return json.loads(stdout[idx:])


def run_gws(args: list):
    parts = []
    for a in args:
        escaped = a.replace('"', '\\"')
        parts.append(f'"{escaped}"')
    cmd = "gws " + " ".join(parts)
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
        shell=True
    )
    return parse_gws_output(result.stdout)


CALENDAR_ID = os.getenv("CALENDAR_ID")
GMAIL_USER  = os.getenv("GMAIL_USER", "me")
MAX_RESULTS = 5


def get_recent_emails(max_results=MAX_RESULTS):
    print(f"\n📬 Gmail에서 최신 메일 {max_results}개 가져오는 중...")
    data = run_gws([
        "gmail", "users", "messages", "list",
        "--params", json.dumps({"userId": GMAIL_USER, "maxResults": max_results})
    ])
    return data.get("messages", [])


def get_email_content(message_id):
    return run_gws([
        "gmail", "users", "messages", "get",
        "--params", json.dumps({"userId": GMAIL_USER, "id": message_id, "format": "full"})
    ])


def parse_email(email_data):
    headers = email_data.get("payload", {}).get("headers", [])
    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "제목없음")
    sender  = next((h["value"] for h in headers if h["name"] == "From"), "발신자없음")
    date    = next((h["value"] for h in headers if h["name"] == "Date"), "")

    body = ""
    payload = email_data.get("payload", {})
    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain":
                import base64
                data = part.get("body", {}).get("data", "")
                if data:
                    body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                break
    elif payload.get("mimeType") == "text/plain":
        import base64
        data = payload.get("body", {}).get("data", "")
        if data:
            body = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")

    return {"subject": subject, "sender": sender, "date": date, "body": body}


def extract_event_with_claude(email):
    today = datetime.now().strftime("%Y-%m-%d")
    prompt = f"""다음 이메일에서 일정 정보를 추출해줘.
오늘 날짜는 {today}이야.

반드시 아래 JSON 형식으로만 응답해. 다른 말은 하지 마.
일정이 없으면 "has_event": false로 줘.
시간이 명시되지 않은 경우 오전 9시(09:00)를 기본값으로 써줘.

{{
  "has_event": true,
  "summary": "일정 제목",
  "start_datetime": "2026-05-28T10:00:00+09:00",
  "end_datetime": "2026-05-28T11:00:00+09:00",
  "description": "일정 내용 요약",
  "confidence_score": 0.95
}}

발신자: {email['sender']}
제목: {email['subject']}
날짜: {email['date']}
본문:
{email['body'][:2000]}"""

    claude_cmd = "claude.cmd" if sys.platform == "win32" else "claude"
    result = subprocess.run(
        f'{claude_cmd} -p {json.dumps(prompt)} --output-format text',
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        shell=True
    )
    raw = result.stdout.strip()

    try:
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception as e:
        print(f"  ⚠️  JSON 파싱 실패: {e}")
        print(f"  Claude 응답: {raw[:200]}")
        return None


def register_to_calendar(event_data, email):
    confidence = event_data.get("confidence_score", 1.0)
    summary = event_data["summary"]

    if confidence < 0.7:
        summary = f"[확인필요] {summary}"

    resource = {
        "summary": summary,
        "description": (
            f"{event_data.get('description', '')}\n\n"
            f"---\nAI 자동 등록 | 원본 메일: {email['subject']} | 신뢰도: {confidence}"
        ),
        "start": {
            "dateTime": event_data["start_datetime"],
            "timeZone": "Asia/Seoul"
        },
        "end": {
            "dateTime": event_data["end_datetime"],
            "timeZone": "Asia/Seoul"
        }
    }

    result = subprocess.run(
        [GWS, "calendar", "events", _insert_subcmd(), "--params", json.dumps({"calendarId": CALENDAR_ID}), "--json", "-"],
        input=json.dumps(resource, ensure_ascii=False), capture_output=True,
        text=True, encoding="utf-8", errors="replace", shell=False
    )
    return parse_gws_output(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--message-id", help="처리할 특정 메일 ID")
    args = parser.parse_args()

    print("🚀 DAP 파이프라인 시작")
    print(f"   실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   캘린더 ID: {CALENDAR_ID}")
    print(f"   Gmail 계정: {GMAIL_USER}")

    if not CALENDAR_ID:
        print("❌ .env 파일에 CALENDAR_ID가 없습니다.")
        return

    if args.message_id:
        messages = [{"id": args.message_id}]
        print(f"   메일 ID: {args.message_id}")
    else:
        messages = get_recent_emails()

    if not messages:
        print("📭 새 메일 없음")
        return

    success_count = 0
    skip_count = 0

    for msg in messages:
        print(f"\n{'─'*50}")
        email_data = get_email_content(msg["id"])
        email = parse_email(email_data)

        print(f"📧 제목: {email['subject']}")
        print(f"   발신: {email['sender']}")

        print("🤖 Claude가 일정 분석 중...")
        event = extract_event_with_claude(email)

        if not event:
            print("   ❌ 분석 실패 - 스킵")
            skip_count += 1
            continue

        if not event.get("has_event"):
            print("   📭 일정 없음 - 스킵")
            skip_count += 1
            continue

        print(f"   ✅ 일정 발견: {event.get('summary')}")
        print(f"   📅 시작: {event.get('start_datetime')}")
        print(f"   🎯 신뢰도: {event.get('confidence_score')}")
        print("📆 캘린더에 등록 중...")

        result = register_to_calendar(event, email)

        if "id" in result:
            print(f"   ✅ 등록 완료: {result.get('htmlLink', '')}")
            success_count += 1
        else:
            print(f"   ❌ 등록 실패: {result}")
            skip_count += 1

    print(f"\n{'─'*50}")
    print(f"🏁 완료 | 등록: {success_count}개 | 스킵: {skip_count}개")


if __name__ == "__main__":
    main()
