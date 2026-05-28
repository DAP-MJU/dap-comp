# gws CLI 환경 설정 가이드

## 개요
gws CLI (Google Workspace CLI)를 사용해 Gmail 수신 및 Google Calendar 연동 환경을 설정합니다.

## 사전 요구사항
- Node.js v18 이상
- npm
- Mac: Homebrew
- Windows: winget 또는 Google Cloud SDK 설치 관리자

## 설치

### 1. gws CLI 설치 (공통)
```bash
npm install -g @googleworkspace/cli
```

### 2. gcloud CLI 설치

**Mac**
```bash
brew install --cask google-cloud-sdk
```

**Windows**
아래 링크에서 설치 관리자 다운로드 후 실행
https://cloud.google.com/sdk/docs/install#windows
또는 winget 사용
```bash
winget install Google.CloudSDK
```

### 3. PATH 설정

**Mac**
```bash
echo 'export PATH=/opt/homebrew/share/google-cloud-sdk/bin:"$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Windows**
설치 관리자가 자동으로 PATH 설정함. 설치 후 새 터미널(PowerShell) 열면 적용됨.

## 인증 세팅

### 4. gws auth setup 실행
```bash
gws auth setup
```
- Step 1: gcloud CLI 자동 감지
- Step 2: `Login with new account` 선택 → 브라우저에서 구글 계정 로그인
- Step 3: `dap-mju` 프로젝트 선택
- Step 4: Gmail, Google Calendar API 선택
- Step 5: OAuth Client ID / Secret 입력
  (GCP 콘솔 → API 및 서비스 → 사용자 인증 정보에서 확인, 팀 내부 전달)

### 5. 로그인
```bash
gws auth login
```
브라우저에서 본인 구글 계정으로 동의 완료

## 동작 확인

### Gmail 수신함 확인
```bash
gws gmail +triage
```

### Calendar 일정 확인
```bash
gws calendar +agenda
```

## 주의사항
- OAuth Client ID / Secret은 절대 git에 올리지 않는다
- 인증 파일 (`~/.config/gws/`) 도 git에 올리지 않는다
- 테스트 사용자로 등록된 구글 계정만 로그인 가능
- Windows에서 `gws auth login` 실행 시 keyring 오류 발생하면 아래 환경변수 설정 후 재시도
  `set GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=file`

## 버전 정보
- gws: 0.22.5
- gcloud CLI: 569.0.0