import argparse
import subprocess
import json
import os
import shutil
import base64
import re
import html
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

GWS = shutil.which("gws.cmd") or "gws.cmd"

CALENDAR_ID = os.getenv("CALENDAR_ID")
GMAIL_USER = os.getenv("GMAIL_USER", "me")
MAX_RESULTS = 5


def parse_gws_output(stdout: str):
    idx = -1

    for i, ch in enumerate(stdout):
        if ch in ("{", "["):
            idx = i
            break

    if idx == -1:
        raise ValueError(f"JSON을 찾을 수 없음: {stdout[:300]}")

    return json.loads(stdout[idx:])


def run_gws(args: list):
    result = subprocess.run(
        [GWS] + args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False
    )

    if result.returncode != 0:
        print("❌ GWS 실행 실패")
        print("stderr:", result.stderr[:300])
        print("stdout:", result.stdout[:300])
        raise RuntimeError("GWS command failed")

    return parse_gws_output(result.stdout)


def get_recent_emails(max_results=MAX_RESULTS):
    print(f"\n📬 Gmail에서 최신 메일 {max_results}개 가져오는 중...")

    data = run_gws([
        "gmail", "users", "messages", "list",
        "--params", json.dumps({
            "userId": GMAIL_USER,
            "maxResults": max_results
        }, ensure_ascii=False)
    ])

    return data.get("messages", [])


def get_email_content(message_id):
    return run_gws([
        "gmail", "users", "messages", "get",
        "--params", json.dumps({
            "userId": GMAIL_USER,
            "id": message_id,
            "format": "full"
        }, ensure_ascii=False)
    ])


def decode_gmail_body(data: str) -> str:
    if not data:
        return ""

    try:
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    except Exception:
        return ""


def html_to_text(raw_html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw_html, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_plain_text_from_payload(payload):
    if not payload:
        return ""

    mime_type = payload.get("mimeType", "")
    data = payload.get("body", {}).get("data", "")

    if mime_type == "text/plain" and data:
        return decode_gmail_body(data).strip()

    if mime_type == "text/html" and data:
        return html_to_text(decode_gmail_body(data))

    for part in payload.get("parts", []):
        text = extract_plain_text_from_payload(part)
        if text:
            return text

    return ""


def parse_email(email_data):
    headers = email_data.get("payload", {}).get("headers", [])

    subject = next(
        (h["value"] for h in headers if h.get("name", "").lower() == "subject"),
        "제목없음"
    )

    sender = next(
        (h["value"] for h in headers if h.get("name", "").lower() == "from"),
        "발신자없음"
    )

    date = next(
        (h["value"] for h in headers if h.get("name", "").lower() == "date"),
        ""
    )

    payload = email_data.get("payload", {})
    body = extract_plain_text_from_payload(payload)

    print(f"   본문 길이: {len(body)}")
    print(f"   본문 미리보기: {body[:200]}")

    return {
        "subject": subject,
        "sender": sender,
        "date": date,
        "body": body
    }


def make_summary(subject: str, body: str) -> str:
    if subject and subject.strip():
        return subject.strip()

    first_line = body.strip().splitlines()[0] if body.strip() else "일정"
    return first_line[:30]


def extract_event_with_claude(email):
    body = email["body"].strip()
    subject = email["subject"].strip()

    if not body:
        print("  ⚠️  메일 본문이 비어 있음")
        return None

    text = subject + "\n" + body

    month_day = re.search(r"(\d{1,2})월\s*(\d{1,2})일", text)
    time_match = re.search(r"(오전|오후)?\s*(\d{1,2})시(?:\s*(\d{1,2})분)?", text)

    if not month_day:
        return {"has_event": False}

    month = int(month_day.group(1))
    day = int(month_day.group(2))

    if time_match:
        ampm = time_match.group(1)
        hour = int(time_match.group(2))
        minute = int(time_match.group(3) or 0)

        if ampm == "오후" and hour < 12:
            hour += 12

        if ampm == "오전" and hour == 12:
            hour = 0
    else:
        hour = 9
        minute = 0

    try:
        start_datetime = datetime(2026, month, day, hour, minute)
    except ValueError:
        print("  ⚠️  날짜/시간 해석 실패")
        return None

    end_datetime = start_datetime + timedelta(hours=1)

    return {
        "has_event": True,
        "summary": make_summary(subject, body),
        "start_datetime": start_datetime.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "end_datetime": end_datetime.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
        "description": body[:500],
        "confidence_score": 0.8
    }


def clean_text(text: str) -> str:
    return (
        str(text)
        .replace("<", "(")
        .replace(">", ")")
        .replace("&", "and")
        .replace("\r", " ")
    )


def register_to_calendar(event_data, email):
    confidence = event_data.get("confidence_score", 1.0)

    summary = clean_text(event_data.get("summary", "제목없음"))
    email_subject = clean_text(email["subject"])
    sender = clean_text(email["sender"])
    event_description = clean_text(event_data.get("description", ""))

    if confidence < 0.7:
        summary = f"[확인필요] {summary}"

    description = (
        f"{event_description}\n\n"
        f"---\n"
        f"AI 자동 등록\n"
        f"원본 메일 제목: {email_subject}\n"
        f"신뢰도: {confidence}\n"
        f"발신자: {sender}"
    )

    resource = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": event_data["start_datetime"],
            "timeZone": "Asia/Seoul"
        },
        "end": {
            "dateTime": event_data["end_datetime"],
            "timeZone": "Asia/Seoul"
        }
    }

    params = json.dumps({"calendarId": CALENDAR_ID}, ensure_ascii=False)
    body = json.dumps(resource, ensure_ascii=False)

    result = subprocess.run(
        [
            GWS,
            "calendar",
            "events",
            "insert",
            "--params",
            params,
            "--json",
            body
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False
    )

    if result.returncode != 0:
        print("❌ 캘린더 등록 실패")
        print("stderr:", result.stderr[:500])
        print("stdout:", result.stdout[:500])
        return {}

    return parse_gws_output(result.stdout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--message-id", help="처리할 특정 메일 ID")
    args = parser.parse_args()

    print("🚀 DAP 파이프라인 시작")
    print(f"   실행 시각: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   캘린더 ID: {CALENDAR_ID}")
    print(f"   Gmail 계정: {GMAIL_USER}")
    print(f"   GWS 경로: {GWS}")

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
        print(f"\n{'─' * 50}")

        try:
            email_data = get_email_content(msg["id"])
            email = parse_email(email_data)

            print(f"📧 제목: {email['subject']}")
            print(f"   발신: {email['sender']}")

            print("🤖 일정 정보 분석 중...")
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
            print(f"   📅 종료: {event.get('end_datetime')}")
            print(f"   🎯 신뢰도: {event.get('confidence_score')}")
            print("📆 캘린더에 등록 중...")

            result = register_to_calendar(event, email)

            if "id" in result:
                print(f"   ✅ 등록 완료: {result.get('htmlLink', '')}")
                success_count += 1
            else:
                print("   ❌ 등록 실패")
                skip_count += 1

        except Exception as e:
            print(f"   ❌ 처리 중 오류: {e}")
            skip_count += 1

    print(f"\n{'─' * 50}")
    print(f"🏁 완료 | 등록: {success_count}개 | 스킵: {skip_count}개")


if __name__ == "__main__":
    main()