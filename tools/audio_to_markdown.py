#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
오디오 파일에서 텍스트를 추출하여 마크다운 파일로 저장하는 스크립트

이 스크립트는 OpenAI의 Whisper 모델을 사용하여 오디오 파일에서 텍스트를 추출하고,
추출된 텍스트를 마크다운 파일로 저장합니다.

사용법:
    python audio_to_markdown.py
    또는
    python audio_to_markdown.py [오디오_파일_경로]

요구사항:
    - Python 3.7 이상
    - PyTorch
    - OpenAI Whisper
    - FFmpeg (시스템에 설치되어 있어야 함)
"""

import os
import sys
import time
import argparse
import torch
import psutil
from pathlib import Path
from datetime import datetime

# 필요한 라이브러리 확인 및 설치 안내
try:
    import whisper
except ImportError:
    print("오류: OpenAI Whisper 라이브러리가 설치되지 않았습니다.")
    print("다음 명령어로 설치하세요: pip install openai-whisper")
    sys.exit(1)

try:
    import psutil
except ImportError:
    print("경고: psutil 라이브러리가 설치되지 않았습니다.")
    print("시스템 정보 표시를 위해 설치하는 것이 좋습니다: pip install psutil")
    # psutil이 없어도 계속 진행

def check_ffmpeg():
    """FFmpeg가 시스템에 설치되어 있는지 확인합니다."""
    import subprocess
    try:
        subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

def get_device_info():
    """사용 가능한 장치(CPU/GPU) 정보를 반환합니다."""
    info = []

    # CPU 정보
    try:
        cpu_count_physical = psutil.cpu_count(logical=False)
        cpu_count_logical = psutil.cpu_count(logical=True)
        info.append(f"CPU: {cpu_count_physical}코어 {cpu_count_logical}스레드")
    except:
        info.append("CPU: 정보를 가져올 수 없음")

    # GPU 정보
    if torch.cuda.is_available():
        device_name = torch.cuda.get_device_name(0)
        device_count = torch.cuda.device_count()
        cuda_version = torch.version.cuda

        # GPU 메모리 정보
        try:
            gpu_mem_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)  # GB 단위
            info.append(f"GPU: {device_name} ({device_count}개 감지됨)")
            info.append(f"CUDA: {cuda_version}, 메모리: {gpu_mem_total:.2f}GB")
        except:
            info.append(f"GPU: {device_name} ({device_count}개 감지됨)")
            info.append(f"CUDA: {cuda_version}")
    else:
        info.append("GPU: CUDA를 사용할 수 없음")

    return "\n - ".join(info)

def transcribe_audio(audio_path, model_name="medium", use_gpu=True):
    """
    오디오 파일에서 텍스트를 추출합니다.

    Args:
        audio_path (str): 오디오 파일 경로
        model_name (str): 사용할 Whisper 모델 이름 (tiny, base, small, medium, large)
        use_gpu (bool): GPU 사용 여부

    Returns:
        dict: 추출된 텍스트 및 메타데이터
    """
    start_time = time.time()

    # 장치 설정
    device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
    print(f"사용 장치: {device}")

    # 모델 크기 및 성능 정보 표시
    model_info = {
        "tiny": "39M 매개변수, 빠름, 낮은 정확도",
        "base": "74M 매개변수, 중간 속도, 중간 정확도",
        "small": "244M 매개변수, 중간 속도, 좋은 정확도",
        "medium": "769M 매개변수, 느림, 높은 정확도",
        "large": "1550M 매개변수, 매우 느림, 최고 정확도"
    }
    print(f"Whisper {model_name} 모델 로드 중... ({model_info.get(model_name, '')})")

    # 모델 로드
    model = whisper.load_model(model_name, device=device)
    model_load_time = time.time() - start_time
    print(f"모델 로드 완료: {model_load_time:.2f}초 소요")

    # 오디오 파일 처리
    print(f"오디오 파일 처리 중: {os.path.basename(audio_path)}")
    transcribe_start_time = time.time()

    # 한국어에 최적화된 설정
    result = model.transcribe(
        audio_path,
        language="ko",  # 한국어 지정
        task="transcribe",  # 음성-텍스트 변환 작업
        fp16=device == "cuda",  # GPU 사용 시 FP16 정밀도 사용
        verbose=True  # 진행 상황 표시
    )

    transcribe_time = time.time() - transcribe_start_time
    total_time = time.time() - start_time

    # 처리 시간 정보 출력
    print(f"텍스트 추출 완료: {transcribe_time:.2f}초 소요")
    print(f"총 처리 시간: {total_time:.2f}초")

    # 추출된 텍스트 길이 정보
    text_length = len(result["text"])
    segment_count = len(result["segments"]) if "segments" in result else 0
    print(f"추출된 텍스트: {text_length}자, {segment_count}개 세그먼트")

    return result

def save_as_markdown(result, audio_path):
    """
    추출된 텍스트를 마크다운 파일로 저장합니다.

    Args:
        result (dict): Whisper 모델에서 반환된 결과
        audio_path (str): 원본 오디오 파일 경로

    Returns:
        str: 저장된 마크다운 파일 경로
    """
    # 오디오 파일 정보
    audio_file = Path(audio_path)
    audio_dir = audio_file.parent
    audio_name = audio_file.stem

    # 마크다운 파일 경로
    md_path = audio_dir / f"{audio_name}.md"

    # 현재 날짜 및 시간
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 오디오 파일 정보 가져오기
    try:
        import mutagen
        audio_info = ""
        try:
            audio = mutagen.File(audio_path)
            if audio:
                # 오디오 길이 (초)
                duration = audio.info.length if hasattr(audio.info, 'length') else 0
                # 비트레이트
                bitrate = audio.info.bitrate if hasattr(audio.info, 'bitrate') else 0
                # 샘플레이트
                sample_rate = audio.info.sample_rate if hasattr(audio.info, 'sample_rate') else 0

                audio_info = f"- **오디오 길이**: {format_time(duration)}\n"
                if bitrate:
                    audio_info += f"- **비트레이트**: {bitrate // 1000} kbps\n"
                if sample_rate:
                    audio_info += f"- **샘플레이트**: {sample_rate} Hz\n"
        except Exception:
            audio_info = ""  # 오디오 정보를 가져오지 못한 경우 무시
    except ImportError:
        audio_info = ""  # mutagen 라이브러리가 없는 경우 무시

    # 마크다운 내용 생성
    md_content = f"""# {audio_name} 음성 스크립트

- **원본 파일**: {audio_file.name}
- **생성 시간**: {now}
- **처리 모델**: Whisper
{audio_info}
## 스크립트 내용

{result["text"]}

"""

    # 세그먼트 정보가 있는 경우 추가
    if "segments" in result and result["segments"]:
        md_content += "\n## 타임스탬프 세그먼트\n\n"
        for segment in result["segments"]:
            start = segment["start"]
            end = segment["end"]
            text = segment["text"]
            md_content += f"**[{format_time(start)} → {format_time(end)}]** {text}\n\n"

    # 파일 저장
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"마크다운 파일 저장 완료: {md_path}")

    return str(md_path)

def format_time(seconds):
    """초를 [시:분:초] 형식으로 변환합니다."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

def main():
    """메인 함수"""
    print("\n음성 파일 스크립트 추출기 (Whisper 기반)\n" + "-" * 40)

    # 명령줄 인수 파싱
    parser = argparse.ArgumentParser(description="오디오 파일에서 텍스트를 추출하여 마크다운 파일로 저장합니다.")
    parser.add_argument("audio_path", nargs="?", help="오디오 파일 경로 (입력하지 않으면 실행 중 입력 요청)")
    parser.add_argument("--model", choices=["tiny", "base", "small", "medium", "large"], default="medium",
                        help="사용할 Whisper 모델 (기본값: medium)")
    parser.add_argument("--no-gpu", action="store_true", help="GPU를 사용하지 않고 CPU만 사용")
    parser.add_argument("--batch", action="store_true", help="배치 모드: 폴더 내 모든 오디오 파일 처리")

    args = parser.parse_args()

    # FFmpeg 확인
    if not check_ffmpeg():
        print("오류: FFmpeg가 설치되어 있지 않습니다.")
        print("FFmpeg를 설치한 후 다시 시도하세요.")
        print("Windows: https://ffmpeg.org/download.html")
        print("Linux: sudo apt install ffmpeg")
        print("macOS: brew install ffmpeg")
        sys.exit(1)

    # 시스템 정보 출력
    print(f"시스템 정보:\n - {get_device_info()}")
    print("-" * 40)

    # 오디오 파일 경로 가져오기
    audio_path = args.audio_path
    if not audio_path:
        audio_path = input("오디오 파일 경로를 입력하세요 (따옴표로 감싸도 됨): ").strip('"\'')

    # 배치 모드 확인
    if args.batch or os.path.isdir(audio_path):
        process_batch(audio_path, args.model, not args.no_gpu)
        return

    # 단일 파일 처리
    # 파일 존재 여부 확인
    if not os.path.exists(audio_path):
        print(f"오류: 파일을 찾을 수 없습니다: {audio_path}")
        sys.exit(1)

    # 지원되는 오디오 파일 확장자
    supported_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac']
    file_ext = os.path.splitext(audio_path)[1].lower()

    if file_ext not in supported_extensions:
        print(f"경고: '{file_ext}' 확장자는 지원되지 않을 수 있습니다.")
        confirm = input("계속 진행하시겠습니까? (y/n, 기본값: y): ").strip().lower()
        if not confirm or confirm == 'y':
            pass  # 계속 진행
        else:
            print("작업이 취소되었습니다.")
            sys.exit(0)

    # 오디오 파일 처리
    try:
        print("-" * 40)
        # 텍스트 추출
        result = transcribe_audio(audio_path, model_name=args.model, use_gpu=not args.no_gpu)

        # 마크다운 파일로 저장
        md_path = save_as_markdown(result, audio_path)

        print("-" * 40)
        print(f"작업 완료! 마크다운 파일이 생성되었습니다: {md_path}")

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def process_batch(folder_path, model_name="medium", use_gpu=True):
    """폴더 내 모든 오디오 파일을 처리합니다."""
    print(f"\n폴더 처리 모드: {folder_path}")
    print("-" * 40)

    if not os.path.isdir(folder_path):
        print(f"오류: 유효한 폴더가 아닙니다: {folder_path}")
        return

    # 지원되는 오디오 파일 확장자
    supported_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.aac']

    # 폴더 내 오디오 파일 찾기
    audio_files = []
    for ext in supported_extensions:
        audio_files.extend(list(Path(folder_path).glob(f"*{ext}")))
        audio_files.extend(list(Path(folder_path).glob(f"*{ext.upper()}")))

    if not audio_files:
        print(f"오류: 폴더에 지원되는 오디오 파일이 없습니다: {folder_path}")
        return

    # 파일을 이름 순으로 정렬
    audio_files.sort(key=lambda x: x.name)

    print(f"폴더에서 {len(audio_files)}개의 오디오 파일을 찾았습니다:")
    for i, file in enumerate(audio_files):
        print(f"  {i+1}. {file.name}")

    confirm = input(f"\n{len(audio_files)}개 파일을 모두 처리하시겠습니까? (y/n, 기본값: y): ").strip().lower()
    if not confirm or confirm == 'y':
        # 모델 로드 (한 번만)
        print(f"\nWhisper {model_name} 모델 로드 중...")
        device = "cuda" if use_gpu and torch.cuda.is_available() else "cpu"
        model = whisper.load_model(model_name, device=device)

        # 각 파일 처리
        success_count = 0
        error_files = []
        start_time_all = time.time()

        for i, file in enumerate(audio_files):
            file_start_time = time.time()
            print(f"\n[{i+1}/{len(audio_files)}] 처리 중: {file.name}")
            print("-" * 40)

            try:
                # 텍스트 추출 (이미 로드된 모델 사용)
                result = model.transcribe(
                    str(file),
                    language="ko",
                    task="transcribe",
                    fp16=device == "cuda",
                    verbose=False
                )

                # 마크다운 파일로 저장
                save_as_markdown(result, str(file))
                success_count += 1

                # 파일 처리 시간 출력
                file_time = time.time() - file_start_time
                print(f"파일 처리 완료: {file_time:.2f}초 소요")

                # 진행률 출력
                progress = (i + 1) / len(audio_files) * 100
                print(f"전체 진행률: {progress:.1f}% ({i+1}/{len(audio_files)})")

            except Exception as e:
                print(f"오류 발생: {file.name} - {e}")
                error_files.append(file.name)

        # 결과 요약
        total_time = time.time() - start_time_all
        print(f"\n처리 완료: 총 {len(audio_files)}개 중 {success_count}개 성공, {len(error_files)}개 실패")
        print(f"총 소요 시간: {total_time:.2f}초 (파일당 평균: {total_time/len(audio_files):.2f}초)")

        if error_files:
            print("\n실패한 파일:")
            for file in error_files:
                print(f"  - {file}")
    else:
        print("작업이 취소되었습니다.")

if __name__ == "__main__":
    main()
