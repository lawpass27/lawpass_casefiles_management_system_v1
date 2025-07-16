---
created: 2025-07-14 (Monday) 16:53
updated: 2025-07-14 (Monday) 16:53
---
# 크로스 플랫폼 설정 가이드

본 시스템은 Windows, macOS, Linux/WSL 환경을 모두 지원합니다.

## 1. 환경별 초기 설정

### Windows

1. **Poppler 설치**
   ```bash
   # Scoop 사용 (권장)
   scoop install poppler
   
   # 또는 수동 설치
   # https://github.com/oschwartz10612/poppler-windows/releases
   # 다운로드 후 PATH에 bin 폴더 추가
   ```

2. **Google Cloud 자격 증명 설정**
   ```bash
   # 기본 위치에 credentials.json 저장
   mkdir %USERPROFILE%\.config\pdf2text
   copy credentials.json %USERPROFILE%\.config\pdf2text\
   ```

### macOS

1. **Poppler 설치**
   ```bash
   brew install poppler
   ```

2. **Google Cloud 자격 증명 설정**
   ```bash
   mkdir -p ~/.config/pdf2text
   cp credentials.json ~/.config/pdf2text/
   ```

### Linux/WSL

1. **Poppler 설치**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install poppler-utils
   
   # Fedora
   sudo dnf install poppler-utils
   ```

2. **Google Cloud 자격 증명 설정**
   ```bash
   mkdir -p ~/.config/pdf2text
   cp credentials.json ~/.config/pdf2text/
   ```

## 2. 환경 변수 설정

### 방법 1: .env 파일 사용 (권장)

1. `.env.example`을 `.env`로 복사
   ```bash
   cp .env.example .env
   ```

2. 환경에 맞게 수정
   ```bash
   # Windows 예시
   GOOGLE_CLOUD_CREDENTIALS=C:\Users\username\.config\pdf2text\credentials.json
   POPPLER_PATH=C:\Users\username\scoop\apps\poppler\current\bin
   
   # macOS/Linux 예시
   GOOGLE_CLOUD_CREDENTIALS=/home/username/.config/pdf2text/credentials.json
   # POPPLER_PATH= (비워두면 시스템 PATH 사용)
   ```

### 방법 2: 플랫폼별 환경 변수 사용

여러 플랫폼에서 동일한 .env 파일을 사용하려면:

```bash
# Windows 전용
GOOGLE_CLOUD_CREDENTIALS_WINDOWS=C:\Users\username\.config\pdf2text\credentials.json
POPPLER_PATH_WINDOWS=C:\Users\username\scoop\apps\poppler\current\bin

# WSL 전용
GOOGLE_CLOUD_CREDENTIALS_WSL=/home/username/.config/pdf2text/credentials.json
# POPPLER_PATH_WSL= (비워둠)

# macOS 전용
GOOGLE_CLOUD_CREDENTIALS_MAC=/Users/username/.config/pdf2text/credentials.json
# POPPLER_PATH_MAC= (비워둠)
```

### 방법 3: 기본 위치 사용

환경 변수를 설정하지 않으면 자동으로 다음 위치에서 찾습니다:
- Windows: `%USERPROFILE%\.config\pdf2text\credentials.json`
- macOS/Linux: `~/.config/pdf2text/credentials.json`

## 3. 설정 우선순위

시스템은 다음 순서로 설정을 찾습니다:

1. 플랫폼별 환경 변수 (예: `GOOGLE_CLOUD_CREDENTIALS_WSL`)
2. 기본 환경 변수 (예: `GOOGLE_CLOUD_CREDENTIALS`)
3. config.yaml 파일
4. 플랫폼별 기본 경로

## 4. 문제 해결

### 경로 관련 문제

디버그 모드를 활성화하여 경로 확인:
```bash
# .env 파일에 추가
DEBUG=True
```

### Google Cloud Vision API 오류

1. 자격 증명 파일이 올바른 위치에 있는지 확인
2. 파일 권한 확인 (읽기 가능해야 함)
3. API가 활성화되어 있는지 확인

### Poppler 관련 오류

- Windows: Poppler bin 폴더가 PATH에 있거나 POPPLER_PATH로 지정되어야 함
- macOS/Linux: 시스템 패키지 관리자로 설치하면 자동으로 PATH에 추가됨

## 5. 테스트

설정이 올바른지 테스트:
```bash
python steps/step5_casefiles_extractor.py --case-folder "테스트폴더경로" --evidence
```