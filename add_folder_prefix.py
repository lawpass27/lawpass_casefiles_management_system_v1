# -*- coding: utf-8 -*-
"""
표준 하위 폴더 내의 파일들에 폴더 이름을 접두어로 추가하는 스크립트.
(0_INBOX 폴더는 제외)
이미 접두어가 있거나 파일 이름에 공백이 있는 경우 처리.
"""

import os
import sys
import argparse
import logging
from datetime import datetime # Timestamp for collision handling

# --- Optional Rich Integration ---
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.theme import Theme
    RICH_AVAILABLE = True
    custom_theme = Theme({
        "info": "cyan",
        "success": "bold green",
        "warning": "yellow",
        "error": "bold red",
        "skipped": "dim cyan", # Style for skipped files/folders
        "filename_original": "dim yellow",
        "filename_new": "yellow",
        "question": "bold yellow"
    })
    console = Console(theme=custom_theme)
except ImportError:
    RICH_AVAILABLE = False
    console = None
    print("Rich 라이브러리가 설치되어 있지 않습니다. 기본 출력을 사용합니다.")
    print("Rich 설치 방법: pip install rich")
# --- End Optional Rich Integration ---

# 처리 대상 표준 폴더 목록 (이 리스트는 여전히 모든 폴더를 포함)
STANDARD_FOLDERS = [
    "0_INBOX",
    "1_기본정보",
    "2_사건개요",
    "3_기준판례",
    "4_사실관계",
    "5_관련법리",
    "6_논리구성",
    "7_제출증거",
    "8_제출서면",
    "9_판결"
]

# 로깅 설정 함수
def setup_logging(level="INFO"):
    """로깅 설정"""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    for handler in logger.handlers[:]: logger.removeHandler(handler)
    if RICH_AVAILABLE:
        from rich.logging import RichHandler
        handler = RichHandler(rich_tracebacks=True, markup=True, console=console)
    else:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(log_format, date_format)
        handler.setFormatter(formatter)
    logger.addHandler(handler)

# 메시지 출력 함수
def print_message(message, level="info"):
    """콘솔 메시지 출력 (Rich 지원)"""
    if RICH_AVAILABLE:
        style = level if level in ["info", "success", "warning", "error", "skipped", "filename_original", "filename_new", "question"] else "info"
        console.print(f"[{style}]{message}[/]")
    else:
        prefix = f"[{level.upper()}] " if level != "info" else ""
        print(f"{prefix}{message}")

# 사용자 입력 함수
def get_case_folder_from_input():
    """사용자로부터 사건 폴더 경로 입력 받기"""
    prompt = "접두어를 추가할 파일들이 있는 상위 '사건 폴더' 경로를 입력하세요: "
    if RICH_AVAILABLE:
        case_folder = console.input(f"[question]{prompt}[/]")
    else:
        case_folder = input(prompt)
    case_folder = case_folder.strip('"\'')
    return os.path.normpath(case_folder)

def add_folder_prefix_to_files(case_folder, target_folders):
    """대상 폴더 내 파일들에 폴더 이름 접두어 추가"""
    if not case_folder or not os.path.isdir(case_folder):
        logging.error(f"유효하지 않거나 존재하지 않는 사건 폴더: {case_folder}")
        print_message(f"오류: '{case_folder}'는 유효한 폴더가 아닙니다.", "error")
        return 0, 0, 0 # renamed_count, skipped_count, error_count

    renamed_count = 0
    skipped_count = 0 # 파일 단위 스킵 카운트
    skipped_folder_count = 0 # 폴더 단위 스킵 카운트
    error_count = 0
    total_files_checked = 0

    print_message(f"\n'{case_folder}' 내 표준 폴더의 파일명에 접두어 추가 작업을 시작합니다...", "info")

    # 대상 표준 폴더들을 순회
    for folder_name in target_folders:
        # *** 수정된 부분: 0_INBOX 폴더 건너뛰기 ***
        if folder_name == "0_INBOX":
            logging.info(f"'{folder_name}' 폴더는 접두어 추가 작업에서 제외됩니다. 건너<0xEB><0x9B><0x84>니다.")
            print_message(f"\n[skipped]ℹ️ '{folder_name}' 폴더는 건너<0xEB><0x9B><0x84>니다 (처리 제외 대상).[/]", "skipped")
            skipped_folder_count += 1
            continue # 다음 폴더로 이동
        # *** 수정 완료 ***

        folder_path = os.path.join(case_folder, folder_name)
        prefix_to_add = folder_name + "_" # 추가할 접두어 (예: "1_기본정보_")

        # 대상 폴더가 존재하는지, 그리고 디렉토리인지 확인
        if not os.path.isdir(folder_path):
            logging.warning(f"표준 폴더를 찾을 수 없거나 디렉토리가 아님: {folder_path}. 건너<0xEB><0x9B><0x84>니다.")
            # 사용자에게는 별도 메시지 없이 로그만 남김 (0_INBOX 제외하고는 존재해야 함)
            continue # 다음 표준 폴더로

        print_message(f"\n[{folder_name}] 폴더 처리 중...", "info")
        try:
            # 폴더 내의 모든 항목(파일 및 디렉토리) 목록 가져오기
            items = os.listdir(folder_path)
        except OSError as e:
            logging.error(f"폴더 읽기 오류: {folder_path} - {e}")
            print_message(f"  ❌ 오류: '{folder_name}' 폴더를 읽을 수 없습니다 ({e}).", "error")
            error_count += 1 # 폴더 접근 오류도 오류 카운트에 포함
            continue # 다음 표준 폴더로

        # 폴더 내 각 항목 처리
        processed_in_folder = False # 현재 폴더에서 파일 처리 여부 플래그
        for filename in items:
            original_file_path = os.path.join(folder_path, filename)

            # 항목이 파일인지 확인 (디렉토리는 무시)
            if not os.path.isfile(original_file_path):
                continue

            total_files_checked += 1
            processed_in_folder = True # 파일이 하나라도 있으면 처리 시작

            # 1. 이미 접두어가 붙어 있는지 확인
            if filename.startswith(prefix_to_add):
                logging.info(f"접두어 이미 존재, 건너<0xEB><0x9B><0x84>: {filename}")
                print_message(f"  [skipped]ℹ️ 건너<0xEB><0x9B><0x84> (이미 접두어 존재):[/] [filename_original]{filename}[/]", "skipped")
                skipped_count += 1
                continue

            # 2. 접두어가 없는 경우, 새 파일명 생성 (공백 제거 포함)
            filename_no_spaces = filename.replace(" ", "")
            new_filename = prefix_to_add + filename_no_spaces

            # 생성될 새 파일 경로
            new_file_path = os.path.join(folder_path, new_filename)

            # 3. 이름 변경 시도 전, 새 파일명이 이미 존재하는지 확인 (파일명 충돌 방지)
            if os.path.exists(new_file_path):
                # 충돌 시, 파일명 뒤에 타임스탬프 추가하여 고유성 확보 시도
                base, ext = os.path.splitext(new_filename)
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f') # 밀리초까지 추가하여 고유성 강화
                unique_new_filename = f"{base}_{timestamp}{ext}"
                unique_new_file_path = os.path.join(folder_path, unique_new_filename)

                logging.warning(f"새 파일명 충돌: '{new_filename}'. 고유 이름 시도: '{unique_new_filename}'")
                print_message(f"  [warning]⚠️ 경고: 새 파일명 '{new_filename}'이 이미 존재합니다. 고유 이름으로 변경 시도...", "warning")
                new_filename = unique_new_filename # 고유 파일명 사용
                new_file_path = unique_new_file_path

                 # 타임스탬프를 추가한 이름도 충돌하는 극히 드문 경우 최종 에러 처리
                if os.path.exists(new_file_path):
                    logging.error(f"고유 파일명 생성 실패 (타임스탬프 충돌): {new_file_path}")
                    print_message(f"  ❌ 오류: 고유 파일명 '{new_filename}'도 이미 존재하여 변경할 수 없습니다.", "error")
                    error_count += 1
                    continue # 다음 파일로

            # 4. 파일 이름 변경 실행
            try:
                os.rename(original_file_path, new_file_path)
                logging.info(f"파일명 변경: '{filename}' -> '{new_filename}'")
                # 변경 전후 파일명을 명확히 보여줌
                if filename != filename_no_spaces: # 공백 제거가 발생했는지 여부
                     print_message(f"  [success]✅ 변경됨 (공백제거+접두어):[/]\n    [filename_original]'{filename}'[/] -> [filename_new]'{new_filename}'[/]", "success")
                else:
                     print_message(f"  [success]✅ 변경됨 (접두어):[/]\n    [filename_original]'{filename}'[/] -> [filename_new]'{new_filename}'[/]", "success")
                renamed_count += 1
            except OSError as e:
                logging.error(f"파일명 변경 실패: '{filename}' -> '{new_filename}' - {e}")
                print_message(f"  ❌ 오류: '{filename}' 이름 변경 실패 ({e}).", "error")
                error_count += 1

        # 현재 폴더에 처리할 파일이 하나도 없었을 경우 메시지 출력
        if not processed_in_folder and os.path.isdir(folder_path):
             print_message(f"  [info]처리할 파일 없음.[/]", "info")


    print_message(f"\n총 {total_files_checked}개 파일 확인 완료.", "info")
    # 이제 skipped_count는 파일 단위 스킵만 의미, 폴더 스킵은 skipped_folder_count 사용
    return renamed_count, skipped_count, error_count


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(description='표준 폴더(0_INBOX 제외) 내 파일들에 폴더 이름 접두어를 추가합니다 (공백 제거 포함).')
    parser.add_argument('case_folder', nargs='?', default=None, help='작업을 수행할 상위 사건 폴더 경로 (선택 사항)')
    parser.add_argument('--debug', action='store_true', help='디버그 로깅 활성화')

    args = parser.parse_args()

    log_level = "DEBUG" if args.debug else "INFO"
    setup_logging(log_level)

    case_folder_path = args.case_folder
    if not case_folder_path:
        case_folder_path = get_case_folder_from_input()

    if not case_folder_path:
         print_message("오류: 사건 폴더 경로가 지정되지 않았습니다. 스크립트를 종료합니다.", "error")
         return 1 # Indicate error

    # 접두어 추가 함수 실행
    renamed, skipped_files, errors = add_folder_prefix_to_files(case_folder_path, STANDARD_FOLDERS)

    # 결과 요약 출력
    summary_title = "파일 접두어 추가 결과 요약"
    summary_lines = [
        f"대상 경로: {case_folder_path}",
        f"- 이름 변경된 파일 수: {renamed}개",
        f"- 건너<0xEB><0x9B><0x84>뛴 파일 수 (이미 접두어 존재): {skipped_files}개",
        f"- 오류 발생 건수: {errors}개",
        f"('0_INBOX' 폴더는 처리 대상에서 제외됨)" # 제외 정보 명시
    ]
    summary_text = "\n".join(summary_lines)

    # 최종 결과 메시지 및 스타일 결정
    if errors > 0:
        final_message = "파일 접두어 추가 작업 중 오류가 발생했습니다."
        border_style = "red"
        final_style = "error"
        exit_code = 1
    elif renamed > 0:
        final_message = "파일 접두어 추가 작업이 성공적으로 완료되었습니다."
        border_style = "green"
        final_style = "success"
        exit_code = 0
    elif skipped_files > 0:
         final_message = "모든 해당 파일에 이미 접두어가 적용되어 있거나 처리할 파일이 없습니다 ('0_INBOX' 제외)."
         border_style = "yellow"
         final_style = "warning"
         exit_code = 0
    else:
         final_message = "표준 폴더('0_INBOX' 제외) 내에 처리할 파일이 없습니다."
         border_style = "blue"
         final_style = "info"
         exit_code = 0


    # Rich 또는 기본 print로 결과 출력
    if RICH_AVAILABLE:
         console.print(Panel(summary_text, title=summary_title, border_style=border_style, padding=(1, 2)))
         print_message(f"\n{final_message}", level=final_style)
    else:
        print(f"\n--- {summary_title} ---")
        print(summary_text)
        print(f"\n{final_message}")

    return exit_code

if __name__ == "__main__":
    sys.exit(main())