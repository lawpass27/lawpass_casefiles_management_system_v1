# pack_legal_case_interactive.py
import os
import sys
import subprocess
import json
from datetime import datetime
import pytz
import time

# 설정
VAULT_PATH = r"F:\\내 드라이브\\LifewithAI-20250120"
OUTPUT_PATH = r"F:\\내 드라이브\\LifewithAI-20250120\\Legalcases_repomix"
REPOMIX_PATH = r"D:\\Claude_MCP_Servers\\repomix\\bin\\repomix.cjs"

# 법률 폴더 목록
LEGAL_FOLDERS = [
    'Legaladvises',
    'Legalcases',
    'Legalcases_(주)대구농산',
    'Legalcases_(주)리하온'
]

def get_legal_cases():
    """모든 법률 사건 폴더 목록을 가져옵니다."""
    all_case_folders = []

    for legal_folder in LEGAL_FOLDERS:
        legal_folder_path = os.path.join(VAULT_PATH, legal_folder)

        try:
            if os.path.exists(legal_folder_path):
                entries = [entry for entry in os.listdir(legal_folder_path)
                          if os.path.isdir(os.path.join(legal_folder_path, entry))]

                case_folders = [
                    {
                        "name": entry,
                        "path": f"{legal_folder}/{entry}",
                        "parentFolder": legal_folder
                    }
                    for entry in entries
                ]

                all_case_folders.extend(case_folders)
        except Exception as e:
            print(f"폴더 접근 오류: {legal_folder_path} - {str(e)}")

    # 결과 정렬 (부모 폴더별로 그룹화)
    all_case_folders.sort(key=lambda x: (x["parentFolder"], x["name"]))

    return all_case_folders

def pack_legal_case(case_path):
    """사건 폴더를 패키징합니다."""
    # 사건 폴더 이름 추출
    case_name = os.path.basename(case_path)

    # 현재 날짜와 시간 (서울 시각)
    seoul_timezone = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_timezone)
    timestamp = now.strftime("%Y%m%d%H%M")

    # 출력 파일 경로
    output_file = os.path.join(OUTPUT_PATH, f"{case_name}_{timestamp}.txt")

    # 출력 디렉토리 생성
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # Repomix 실행
    try:
        print(f"사건 폴더 압축 중: {case_path}")
        full_case_path = os.path.join(VAULT_PATH, case_path)

        # Node.js 실행 명령어
        command = [
            "node",
            REPOMIX_PATH,
            "-o", output_file,
            "--style", "plain",
            full_case_path
        ]

        # 명령어 실행
        subprocess.run(command, check=True)

        print(f"압축 완료: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"오류 발생: {str(e)}")
        return False
    except Exception as e:
        print(f"예상치 못한 오류: {str(e)}")
        return False

def main():
    """메인 함수"""
    print("법률 사건 폴더 패키징 도구")
    print("=========================")

    # 사건 폴더 목록 가져오기
    legal_cases = get_legal_cases()

    # 사건 폴더 목록 출력
    print(f"\n{len(legal_cases)}개의 법률 사건 폴더를 찾았습니다:")

    # 부모 폴더별로 그룹화하여 출력
    current_parent = ""
    for i, case_folder in enumerate(legal_cases):
        if current_parent != case_folder["parentFolder"]:
            current_parent = case_folder["parentFolder"]
            print(f"\n[{current_parent}]")
        print(f"{i + 1}. {case_folder['name']} ({case_folder['path']})")

    # 사용자 입력 받기
    answer = input("\n패키징할 사건 폴더의 번호 또는 경로를 입력하세요: ")

    case_path = ""

    # 번호로 입력한 경우
    if answer.isdigit():
        index = int(answer) - 1
        if 0 <= index < len(legal_cases):
            case_path = legal_cases[index]["path"]
        else:
            print("잘못된 번호입니다.")
            return
    # 경로로 입력한 경우
    else:
        case_path = answer

        # 경로가 존재하는지 확인
        full_path = os.path.join(VAULT_PATH, case_path)
        if not os.path.exists(full_path):
            print(f"경로를 찾을 수 없습니다: {full_path}")
            return

    # 패키징 실행
    success = pack_legal_case(case_path)

    if success:
        print("\n패키징이 성공적으로 완료되었습니다.")
    else:
        print("\n패키징 중 오류가 발생했습니다.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {str(e)}")
