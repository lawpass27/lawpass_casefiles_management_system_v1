# 음성 파일 스크립트 추출기

이 스크립트는 음성 파일에서 텍스트를 추출하여 마크다운 파일로 저장하는 도구입니다.

## 기능

- 음성 파일에서 텍스트 추출 (한국어 지원)
- 추출된 텍스트를 마크다운 파일로 저장
- 타임스탬프 정보 포함
- NVIDIA GPU 가속 지원 (CUDA)
- 오프라인 작동 (인터넷 연결 불필요)
- 단일 파일 또는 폴더 내 모든 음성 파일 일괄 처리

## 요구사항

- Python 3.7 이상
- FFmpeg (시스템에 설치되어 있어야 함)
- 필요한 Python 패키지:
  - openai-whisper
  - torch
  - psutil (선택사항)
  - mutagen (선택사항)

## 설치 방법

1. FFmpeg 설치:
   - Windows: [FFmpeg 다운로드 페이지](https://ffmpeg.org/download.html)에서 다운로드 후 설치
   - Linux: `sudo apt install ffmpeg`
   - macOS: `brew install ffmpeg`

2. 필요한 Python 패키지 설치:
   ```
   pip install openai-whisper torch psutil mutagen
   ```

## 사용 방법

### 기본 사용법

```
python audio_to_markdown.py
```

실행 후 음성 파일 경로를 입력하라는 메시지가 표시됩니다.

### 명령줄 인수 사용

```
python audio_to_markdown.py [음성_파일_경로]
```

음성 파일 경로 대신 폴더 경로를 입력하면 해당 폴더의 모든 음성 파일을 자동으로 처리합니다.

```
python audio_to_markdown.py [음성_파일_폴더_경로]
```

### 추가 옵션

- `--model [모델명]`: 사용할 Whisper 모델 지정 (tiny, base, small, medium, large)
  - 예: `python audio_to_markdown.py --model small`
  - 기본값은 'medium'

- `--no-gpu`: GPU를 사용하지 않고 CPU만 사용
  - 예: `python audio_to_markdown.py --no-gpu`

- `--batch`: 폴더 내 모든 음성 파일 처리 (폴더 경로를 입력하면 자동으로 처리되므로 일반적으로 필요하지 않음)
  - 예: `python audio_to_markdown.py 음성파일폴더경로 --batch`

## 모델 크기 및 성능

| 모델 | 매개변수 | 속도 | 정확도 | 메모리 요구량 |
|------|---------|------|--------|------------|
| tiny | 39M | 매우 빠름 | 낮음 | 낮음 |
| base | 74M | 빠름 | 중간 | 낮음 |
| small | 244M | 중간 | 좋음 | 중간 |
| medium | 769M | 느림 | 높음 | 높음 |
| large | 1550M | 매우 느림 | 최고 | 매우 높음 |

## 출력 파일

스크립트는 입력 음성 파일과 동일한 이름과 위치에 `.md` 확장자를 가진 마크다운 파일을 생성합니다.
마크다운 파일에는 다음 정보가 포함됩니다:

- 원본 파일 정보
- 생성 시간
- 사용된 모델
- 오디오 파일 정보 (길이, 비트레이트, 샘플레이트)
- 추출된 텍스트
- 타임스탬프 세그먼트

## 주의사항

- 큰 모델(medium, large)은 더 정확하지만 처리 시간이 오래 걸립니다.
- GPU 가속을 사용하면 처리 속도가 크게 향상됩니다.
- 음성 파일의 품질이 좋을수록 더 정확한 결과를 얻을 수 있습니다.
- 모델은 처음 실행 시에만 다운로드되며, 이후에는 로컬에 저장된 모델을 사용합니다.
- 폴더 처리 시 파일은 이름 순으로 정렬되어 처리됩니다.
