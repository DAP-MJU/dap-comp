# DAP

> 이메일 속 일정을 감지하고 캘린더까지 연결하는 자동화 파이프라인

DAP는 반복적으로 확인해야 하는 이메일과 일정 등록 과정을 자동화하기 위한 프로젝트입니다.

새로운 Gmail 메시지를 감지하고, 메일 본문에서 일정 정보를 추출한 뒤 Google Calendar에 자동으로 일정을 생성합니다.

---

## Overview

메일로 전달되는 회의, 행사, 약속 등의 일정은 사용자가 직접 내용을 확인하고 다시 캘린더에 입력해야 합니다.

DAP는 이 과정을 하나의 자동화 흐름으로 연결합니다.

**Gmail → New Mail Detection → Email Parsing → Event Extraction → Validation → Google Calendar**

사용자가 메일과 캘린더 사이에서 반복적으로 수행하던 작업을 이벤트 기반 파이프라인으로 자동화하는 것이 핵심입니다.

---

## Key Features

### 1. Real-time Email Detection

Gmail의 새로운 INBOX 메시지를 감지하고 처리가 필요한 메시지만 자동으로 파이프라인에 전달합니다.

- INBOX 기반 신규 메시지 감지
- DRAFT / SENT 메시지 제외
- 신규 메시지 단위 자동 처리

### 2. Email Content Parsing

Gmail 메시지의 MIME Payload를 분석하여 일정 추출에 필요한 텍스트를 정제합니다.

- Plain Text / HTML 이메일 처리
- Base64 URL-safe Decoding
- HTML → Plain Text 변환
- 제목 / 발신자 / 본문 분리

### 3. Event Information Extraction

메일 제목과 본문에서 일정 후보를 탐색하고 캘린더 이벤트 생성에 필요한 구조화된 데이터로 변환합니다.

- 날짜 및 시간 추출
- 시작 / 종료 시간 생성
- 일정 제목 자동 생성
- Confidence Score 기반 검증 구조

### 4. Google Calendar Automation

추출된 일정 정보를 Google Calendar Event 형식으로 변환하여 사용자의 캘린더에 자동 등록합니다.

등록된 일정에는 원본 이메일 정보와 분석 결과를 함께 기록하여 자동 생성된 일정의 출처를 확인할 수 있도록 설계했습니다.

---

## Architecture

<pre>
┌─────────────────────┐
│        Gmail        │
└──────────┬──────────┘
           │
     New Mail Event
           │
           ▼
┌─────────────────────┐
│       Watcher       │
│     watcher.py      │
└──────────┬──────────┘
           │
      Message ID
           │
           ▼
┌─────────────────────┐
│      Pipeline       │
│     pipeline.py     │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
Email Parsing   Event Extraction
     │           │
     └─────┬─────┘
           ▼
   Event Validation
           │
           ▼
┌─────────────────────┐
│   Google Calendar   │
└─────────────────────┘
</pre>

---

## Processing Flow

### 01. Detect

`watcher.py`가 Gmail INBOX의 새로운 메시지를 감지합니다.

### 02. Filter

DRAFT와 SENT 등 처리 대상이 아닌 메시지를 제외합니다.

### 03. Parse

Gmail API 응답에서 제목, 발신자, 본문을 추출하고 HTML 및 Base64 형식의 데이터를 정규화합니다.

### 04. Extract

메일 본문에서 날짜와 시간 정보를 찾아 캘린더 이벤트 형태의 구조화된 데이터로 변환합니다.

### 05. Validate

추출 결과의 Confidence Score를 기준으로 확인이 필요한 일정과 정상 일정을 구분할 수 있도록 설계했습니다.

### 06. Register

최종 이벤트를 Google Calendar에 자동 등록합니다.

---

## Engineering Highlights

### Event-driven Automation

단순히 사용자가 실행하는 스크립트가 아니라 새로운 메일이 도착하면 자동화 파이프라인이 시작되는 구조로 설계했습니다.

`watcher.py`는 이벤트 감지를 담당하고, `pipeline.py`는 실제 데이터 처리와 Calendar 등록을 담당하도록 역할을 분리했습니다.

### Robust Email Parsing

이메일은 단순 문자열이 아니라 MIME 구조와 다양한 Content-Type을 가질 수 있습니다.

DAP는 Payload를 재귀적으로 탐색하여 `text/plain`과 `text/html`을 모두 처리하고, Base64 Decoding과 HTML Normalization을 거쳐 분석 가능한 텍스트로 변환합니다.

### Traceable Automation

자동으로 생성된 일정의 출처와 분석 결과를 다시 확인할 수 있도록 다음 정보를 Calendar Event Description에 함께 저장합니다.

- 원본 이메일 제목
- 발신자
- 추출된 내용
- Confidence Score

자동화의 편의성뿐만 아니라 결과를 사용자가 다시 검증할 수 있도록 설계했습니다.

### Fault Isolation

개별 이메일 처리 과정에서 오류가 발생하더라도 전체 파이프라인이 중단되지 않도록 메시지 단위로 예외를 격리했습니다.

---

## Tech Stack

| Category | Technology |
| --- | --- |
| Language | Python |
| Google Workspace | Gmail, Google Calendar |
| Integration | Google Workspace CLI |
| Configuration | python-dotenv |
| Data Processing | JSON, MIME Parsing, Base64 |
| Process Control | Python subprocess |
| AI / API | Anthropic SDK *(Integration in progress)* |

---

## Project Structure

<pre>
dap-comp/
├── watcher.py
├── pipeline.py
├── requirements.txt
├── docs/
└── README.md
</pre>

### `watcher.py`

Gmail의 신규 메시지를 감지하고 처리할 메시지를 Pipeline으로 전달합니다.

### `pipeline.py`

메일 조회부터 본문 파싱, 일정 추출, Google Calendar 등록까지 핵심 처리 흐름을 담당합니다.

---

## Roadmap

- [ ] LLM 기반 자연어 일정 정보 추출
- [ ] 다양한 날짜/시간 표현 처리
- [ ] 일정 중복 감지
- [ ] Confidence 기반 사용자 확인 Flow
- [ ] 일정 수정/취소 이메일 자동 반영
- [ ] 반복 일정 및 다중 일정 추출
- [ ] 사용자 인터페이스 구축

---

## What I Learned

DAP를 개발하며 단순 API 연동을 넘어 서로 다른 서비스 사이의 반복 업무를 하나의 자동화 파이프라인으로 연결하는 방법을 고민했습니다.

특히 **이벤트 감지 → 비정형 이메일 데이터 파싱 → 구조화된 일정 데이터 생성 → 외부 서비스 자동 실행**까지 이어지는 End-to-End Workflow를 직접 구현했습니다.
