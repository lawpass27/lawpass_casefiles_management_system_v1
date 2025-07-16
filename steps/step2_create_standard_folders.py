# -*- coding: utf-8 -*-
"""
지정된 사건 폴더 내에 표준 하위 폴더 구조를 생성하는 스크립트.
"""

import os
import sys
import argparse
import logging
import platform

# --- Optional Rich Integration ---
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.theme import Theme # Theme import 추가
    RICH_AVAILABLE = True
    # Define styles for Rich consistent with other scripts
    custom_theme = Theme({ # Theme 객체 사용
        "info": "cyan",
        "success": "bold green",
        "warning": "yellow",
        "error": "bold red",
        "question": "bold yellow"
    })
    console = Console(theme=custom_theme) # 생성자에 theme 적용
except ImportError:
    RICH_AVAILABLE = False
    console = None
    print("Rich 라이브러리가 설치되어 있지 않습니다. 기본 출력을 사용합니다.")
    print("Rich 설치 방법: pip install rich")
# --- End Optional Rich Integration ---

def get_cross_platform_path(windows_path):
    """
    Windows 경로를 현재 시스템에 맞는 경로로 변환합니다.
    WSL 환경에서는 /mnt/d/ 형식으로, Windows에서는 그대로 사용합니다.
    """
    system = platform.system()
    
    # WSL 환경 감지
    is_wsl = 'microsoft' in platform.uname().release.lower() or 'WSL' in platform.uname().release
    
    if system == "Linux" and is_wsl:
        # WSL 환경: D:\\ -> /mnt/d/
        if windows_path.startswith("D:\\"):
            return windows_path.replace("D:\\", "/mnt/d/").replace("\\", "/")
        elif windows_path.startswith("C:\\"):
            return windows_path.replace("C:\\", "/mnt/c/").replace("\\", "/")
        else:
            # 다른 드라이브의 경우 일반적인 패턴 적용
            drive_letter = windows_path[0].lower()
            return windows_path.replace(f"{windows_path[0]}:\\", f"/mnt/{drive_letter}/").replace("\\", "/")
    else:
        # Windows 또는 기타 환경: 그대로 사용
        return windows_path

# 생성할 표준 폴더 목록
REQUIRED_FOLDERS = [
    "0_INBOX",  
    "1_기본정보",
    "2_사건개요",
    "3_사실관계",
    "4_기준판례",
    "5_관련법리",
    "6_논리구성",
    "7_제출증거",
    "8_제출서면",
    "9_판결",
    "원본폴더",
    "절차관련"
]

# 로깅 설정 함수
def setup_logging(level="INFO"):
    """로깅 설정"""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 로거 가져오기 및 레벨 설정
    logger = logging.getLogger()
    logger.setLevel(numeric_level)

    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 핸들러 생성 및 추가
    if RICH_AVAILABLE:
        from rich.logging import RichHandler
        # Use the console object created earlier for RichHandler
        handler = RichHandler(rich_tracebacks=True, markup=True, console=console)
    else:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(log_format, date_format)
        handler.setFormatter(formatter)

    logger.addHandler(handler)

def print_message(message, level="info"):
    """콘솔 메시지 출력 (Rich 지원)"""
    if RICH_AVAILABLE:
        # Ensure level maps to a defined style in the theme or use default
        style = level if level in ["info", "success", "warning", "error", "question"] else "info"
        console.print(f"[{style}]{message}[/]")
    else:
        # 간단한 프리픽스로 레벨 표시
        prefix = f"[{level.upper()}] " if level != "info" else ""
        print(f"{prefix}{message}")

def get_case_folder_from_input():
    """사용자로부터 사건 폴더 경로 입력 받기"""
    # 먼저 case_path.txt 파일에서 경로 읽기 시도
    if os.path.exists("case_path.txt"):
        try:
            with open("case_path.txt", "r", encoding="utf-8") as f:
                saved_path = f.read().strip()
                if saved_path:
                    prompt = f"\ncase_path.txt에 저장된 경로: {saved_path}\n이 경로를 사용하시겠습니까? (y/n, 기본값: y): "
                    if RICH_AVAILABLE:
                        use_saved = console.input(f"[question]{prompt}[/]").lower() or 'y'
                    else:
                        use_saved = input(prompt).lower() or 'y'
                    
                    if use_saved == 'y':
                        return saved_path
        except Exception as e:
            logging.warning(f"case_path.txt 파일 읽기 오류: {e}")
    
    # 저장된 경로가 없거나 사용하지 않는 경우 새로 입력 받기
    prompt = "생성할 폴더의 상위 '사건 폴더' 경로를 입력하세요: "
    if RICH_AVAILABLE:
        # *** 수정된 부분: 직접 마크업 사용 ***
        case_folder = console.input(f"[question]{prompt}[/]")
    else:
        case_folder = input(prompt)
    # 따옴표 제거 및 경로 정규화
    case_folder = case_folder.strip('"\'')
    return os.path.normpath(case_folder)

def create_standard_folders(case_folder, folders_to_create):
    """지정된 경로에 표준 폴더 생성"""
    if not case_folder:
        logging.error("사건 폴더 경로가 제공되지 않았습니다.")
        print_message("오류: 사건 폴더 경로가 필요합니다.", "error")
        return False, 0, 0 # success, created_count, exist_count

    created_count = 0
    exist_count = 0
    errors = []

    # 1. 기본 사건 폴더 존재 확인 및 생성 (사용자 확인 추가)
    if not os.path.exists(case_folder):
        prompt = f"경로 '{case_folder}'가 존재하지 않습니다. 생성하시겠습니까? (y/n): "
        if RICH_AVAILABLE:
             # *** 수정된 부분: 직접 마크업 사용 ***
             confirm_creation = console.input(f"[question]{prompt}[/]").lower()
        else:
             confirm_creation = input(prompt).lower()

        if confirm_creation == 'y':
            try:
                os.makedirs(case_folder)
                logging.info(f"기본 사건 폴더 생성: {case_folder}")
                print_message(f"기본 사건 폴더 생성 완료: {case_folder}", "success")
            except OSError as e:
                logging.error(f"기본 사건 폴더 생성 실패: {case_folder} - {e}")
                print_message(f"오류: 기본 사건 폴더를 생성할 수 없습니다. ({e})", "error")
                return False, 0, 0
        else:
            print_message("기본 사건 폴더 생성이 취소되었습니다.", "warning")
            return False, 0, 0
    elif not os.path.isdir(case_folder):
        logging.error(f"제공된 경로는 폴더가 아닙니다: {case_folder}")
        print_message(f"오류: '{case_folder}'는 폴더가 아닙니다.", "error")
        return False, 0, 0

    # 2. 하위 폴더 생성
    print_message(f"\n'{case_folder}' 내에 표준 폴더 생성을 시작합니다...", "info")
    for folder_name in folders_to_create:
        folder_path = os.path.join(case_folder, folder_name)
        try:
            # 폴더 존재 여부 확인
            if not os.path.exists(folder_path):
                # 존재하지 않으면 생성
                os.makedirs(folder_path) # makedirs는 중간 경로도 생성 가능
                logging.info(f"폴더 생성: {folder_path}")
                print_message(f"  ✅ 생성됨: {folder_name}", "success")
                created_count += 1
            else:
                # 이미 존재하는 경우 (추가 확인: 디렉토리인지?)
                if not os.path.isdir(folder_path):
                     # 존재하지만 폴더가 아닌 경우 오류 처리
                     logging.error(f"경로에 이미 파일이 존재합니다: {folder_path}")
                     print_message(f"  ❌ 오류: '{folder_name}' 위치에 이미 파일이 존재합니다.", "error")
                     errors.append(f"'{folder_name}' 생성 실패: 해당 위치에 파일 존재")
                else:
                    # 이미 폴더로 존재하는 경우, 로그 남기고 넘어감
                    logging.warning(f"폴더 이미 존재: {folder_path}")
                    print_message(f"  ℹ️ 이미 존재: {folder_name}", "warning")
                    exist_count += 1
        except OSError as e:
            # 폴더 생성 중 발생할 수 있는 다른 OS 오류 처리
            logging.error(f"폴더 생성 실패: {folder_path} - {e}")
            print_message(f"  ❌ 오류 ({folder_name}): {e}", "error")
            errors.append(f"'{folder_name}' 생성 실패: {e}")

    if errors:
        print_message("\n일부 폴더 생성 중 오류 발생:", "error")
        for error in errors:
            print_message(f"- {error}", "error")
        # 오류가 하나라도 있으면 False 반환
        return False, created_count, exist_count
    else:
        # 모든 작업이 오류 없이 완료된 경우
        return True, created_count, exist_count

def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='지정된 사건 폴더 내에 표준 하위 폴더 구조를 생성합니다.')
    parser.add_argument('case_folder', nargs='?', default=None, help='표준 폴더들을 생성할 상위 사건 폴더 경로 (선택 사항)')
    parser.add_argument('--debug', action='store_true', help='디버그 로깅 활성화')

    args = parser.parse_args()

    # 로깅 설정
    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(log_level)

    # 사건 폴더 경로 결정
    case_folder_path = args.case_folder
    if not case_folder_path:
        case_folder_path = get_case_folder_from_input()
    
    # Windows 경로를 크로스플랫폼 경로로 변환 (필요한 경우)
    if case_folder_path and '\\' in case_folder_path:
        # Windows 형식 경로인 경우 변환
        case_folder_path = get_cross_platform_path(case_folder_path)

    if not case_folder_path:
         print_message("오류: 사건 폴더 경로가 지정되지 않았습니다. 스크립트를 종료합니다.", "error")
         return 1 # Indicate error

    # 폴더 생성 실행
    success, created, existed = create_standard_folders(case_folder_path, REQUIRED_FOLDERS)

    # 결과 요약 출력
    total_required = len(REQUIRED_FOLDERS)
    failed_count = total_required - created - existed # 실패/오류 개수 계산
    summary_title = "폴더 생성 결과 요약"
    summary_lines = [
        f"대상 경로: {case_folder_path}",
        f"총 {total_required}개 표준 폴더 확인:",
        f"- 새로 생성된 폴더: {created}개",
        f"- 이미 존재하는 폴더: {existed}개",
        f"- 생성 실패 또는 오류: {failed_count}개"
    ]

    summary_text = "\n".join(summary_lines)

    if success:
        final_message = "표준 폴더 구조 생성이 성공적으로 완료되었습니다."
        border_style = "green"
        exit_code = 0
        if created == 0 and existed == total_required:
            final_message = "모든 표준 폴더가 이미 존재합니다. 추가 작업 없음."
            border_style = "yellow"
        elif created > 0 :
             pass # 기본 성공 메시지 사용
        else: # created == 0 and existed < total_required (이 경우는 success=True인데 이상한 경우)
             final_message = "작업 완료 (변경된 사항 없음)."
             border_style = "blue" # 정보성 메시지로 변경

    else:
        final_message = "오류가 발생하여 폴더 생성 작업이 실패했거나 부분적으로만 성공했습니다. 위 메시지나 로그를 확인하십시오."
        border_style = "red"
        exit_code = 1

    # Rich 또는 기본 print로 결과 출력
    if RICH_AVAILABLE:
         console.print(Panel(summary_text, title=summary_title, border_style=border_style, padding=(1, 2)))
         # 최종 메시지 스타일 결정 (오류 시 error, 모두 존재 시 warning, 성공 시 success)
         final_style = "error" if exit_code != 0 else \
                       "warning" if created == 0 and existed == total_required else "success"
         print_message(f"\n{final_message}", level=final_style)
    else:
        print(f"\n--- {summary_title} ---")
        print(summary_text)
        print(f"\n{final_message}")

    return exit_code

if __name__ == "__main__":
    sys.exit(main())