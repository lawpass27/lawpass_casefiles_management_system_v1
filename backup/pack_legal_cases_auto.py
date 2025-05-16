import os
import sys
import subprocess
import json
import hashlib
from datetime import datetime
import pytz
import time
import re
import multiprocessing

# 설정
VAULT_PATH = r"D:\\GoogleDriveStreaming\\내 드라이브\\LifewithAI-20250120"
OUTPUT_PATH = r"D:\\GoogleDriveStreaming\\내 드라이브\\LifewithAI-20250120\\Legalcases_repomix"
REPOMIX_PATH = r"D:\\Claude_MCP_Servers\\repomix\\bin\\repomix.cjs"
LEGAL_FOLDERS = [
    "Legaladvises",
    "Legalcases",
    "Legalcases_(주)대구농산",
    "Legalcases_(주)리하온",
]
BACKUP_FOLDER_NAME = "_backup"

def collect_files_and_hashes(directory_path, base_path, file_hashes_data, current_file_hashes, changed_files_detected, debug_log_file):
    """재귀적으로 디렉토리를 탐색하고 파일 해시를 수집합니다."""
    try:
        entries = os.listdir(directory_path) # os.scandir 대신 os.listdir 사용
        sorted_entries = sorted(entries) # 이름으로 정렬

        for entry_name in sorted_entries:
            full_path = os.path.join(directory_path, entry_name)
            relative_path = os.path.relpath(full_path, base_path)

            if os.path.isfile(full_path): # 파일인지 확인
                debug_log_file.write(f"DEBUG: listdir로 찾은 파일: {full_path}\n") # 파일에 기록
                # print(f"DEBUG: listdir로 찾은 파일: {full_path}") # 터미널 출력 (선택 사항)

                if entry_name == ".debug_log.txt" or os.path.basename(directory_path) == ".hashes":
                     continue # 디버그 로그 파일 및 .hashes 디렉토리 내 파일 무시

                try:
                    current_mtime = os.path.getmtime(full_path) # 수정 시간 가져오기
                    previous_info = file_hashes_data.get(relative_path)

                    print(f"DEBUG: 파일: {relative_path}") # 디버깅 출력
                    debug_log_file.write(f"DEBUG: 파일: {relative_path}\n") # 파일에 기록
                    print(f"DEBUG: current_mtime: {current_mtime}") # 디버깅 출력
                    debug_log_file.write(f"DEBUG: current_mtime: {current_mtime}\n") # 파일에 기록
                    print(f"DEBUG: previous_info: {previous_info}") # 디버깅 출력
                    debug_log_file.write(f"DEBUG: previous_info: {previous_info}\n") # 파일에 기록


                    # 파일 내용 해시 계산
                    with open(full_path, "rb") as f:
                        content = f.read()
                    hasher = hashlib.md5()
                    hasher.update(content)
                    current_file_hash = hasher.hexdigest() # <-- 여기서 current_file_hash가 할당됨

                    print(f"DEBUG: current_file_hash: {current_file_hash}") # 디버깅 출력  <-- 이동
                    debug_log_file.write(f"DEBUG: current_file_hash: {current_file_hash}\n") # 파일에 기록 <-- 이동


                    current_file_hashes[relative_path] = {"hash": current_file_hash, "mtime": current_mtime}

                    # 이전 정보와 비교하여 변경 감지
                    if not previous_info or previous_info.get("mtime") != current_mtime or previous_info.get("hash") != current_file_hash:
                        changed_files_detected[0] = True # 리스트를 사용하여 변경 가능한 객체로 전달
                        print(f"변경 감지: {relative_path}")
                        debug_log_file.write(f"DEBUG: 변경 감지: {relative_path}\n") # 파일에 기록


                except Exception as e:
                    print(f"파일 정보 읽기 또는 해시 계산 오류: {full_path} - {str(e)}")
                    debug_log_file.write(f"DEBUG: 파일 정보 읽기 또는 해시 계산 오류: {full_path} - {str(e)}\n") # 파일에 기록
                    # 오류 발생 시 해당 파일은 무시하고 계속 진행
                    continue

            elif os.path.isdir(full_path): # 디렉토리인지 확인
                if entry_name == ".hashes":
                    continue # .hashes 디렉토리 무시
                # 하위 디렉토리 재귀 호출
                collect_files_and_hashes(full_path, base_path, file_hashes_data, current_file_hashes, changed_files_detected, debug_log_file)

    except Exception as e:
        print(f"디렉토리 탐색 오류: {directory_path} - {str(e)}")
        debug_log_file.write(f"DEBUG: 디렉토리 탐색 오류: {directory_path} - {str(e)}\n") # 파일에 기록
        # 오류 발생 시 해당 디렉토리는 무시하고 계속 진행


def calculate_hash(folder_path):
    """폴더 구조, 파일 내용 및 수정 시간을 기반으로 해시값을 계산합니다."""
    full_folder_path = os.path.join(VAULT_PATH, folder_path)
    hashes_dir = os.path.join(OUTPUT_PATH, ".hashes")
    os.makedirs(hashes_dir, exist_ok=True)
    # 해시 파일 이름은 사건 폴더 이름에서 마지막 숫자 패턴을 제거하고 부모 폴더 이름과 결합하여 생성
    case_name = os.path.basename(folder_path)
    parent_folder = os.path.basename(os.path.dirname(folder_path))
    cleaned_case_name = re.sub(r'_\d+$', '', case_name)
    json_hash_file_name = f"{parent_folder}_{cleaned_case_name}_file_hashes.json"
    json_hash_file_path = os.path.join(hashes_dir, json_hash_file_name)

    file_hashes_data = {}
    previous_folder_hash = None

    # 이전 해시 정보 로드
    if os.path.exists(json_hash_file_path):
        try:
            with open(json_hash_file_path, "r") as f:
                data = json.load(f)
                file_hashes_data = data.get("file_hashes", {})
                previous_folder_hash = data.get("folder_hash")
        except Exception as e:
            print(f"이전 해시 정보 파일 읽기 오류: {json_hash_file_path} - {str(e)}")
            # 오류 발생 시 이전 정보 무시하고 새로 계산
            file_hashes_data = {}
            previous_folder_hash = None

    debug_log_path = ".debug_log.txt" # 디버깅 로그 파일 경로
    current_file_hashes = {}
    changed_files_detected = [False] # 변경된 파일 감지 플래그 (리스트로 변경)

    print(f"DEBUG: 탐색 시작 폴더: {full_folder_path}")
    with open(debug_log_path, "a", encoding="utf-8") as log_file: # 로그 파일에 쓰기 모드로 열기
        log_file.write(f"--- 탐색 시작 폴더: {full_folder_path} ---\n") # 구분선 추가

        print(f"DEBUG: collect_files_and_hashes 호출 전 changed_files_detected[0]: {changed_files_detected[0]}") # 디버깅 출력
        log_file.write(f"DEBUG: collect_files_and_hashes 호출 전 changed_files_detected[0]: {changed_files_detected[0]}\n") # 파일에 기록

        # os.walk 대신 collect_files_and_hashes 호출
        collect_files_and_hashes(full_folder_path, full_folder_path, file_hashes_data, current_file_hashes, changed_files_detected, log_file)

        print(f"DEBUG: collect_files_and_hashes 호출 후 changed_files_detected[0]: {changed_files_detected[0]}") # 디버깅 출력
        log_file.write(f"DEBUG: collect_files_and_hashes 호출 후 changed_files_detected[0]: {changed_files_detected[0]}\n") # 파일에 기록

        log_file.write(f"--- 탐색 종료 ---\n") # 구분선 추가


    # 삭제된 파일 감지
    deleted_files = set(file_hashes_data.keys()) - set(current_file_hashes.keys())
    if deleted_files:
        changed_files_detected[0] = True
        for deleted_file in deleted_files:
            print(f"삭제된 파일 감지: {deleted_file}")

    # 파일별 해시 목록을 정렬하여 폴더 전체 해시 계산
    sorted_file_hashes = sorted(current_file_hashes.items())
    folder_hasher = hashlib.md5()
    for relative_path, info in sorted_file_hashes:
        folder_hasher.update(relative_path.encode('utf-8'))
        folder_hasher.update(info["hash"].encode('utf-8')) # 파일 내용 해시 사용

    current_folder_hash = folder_hasher.hexdigest()

    # 업데이트된 해시 정보 저장
    try:
        with open(json_hash_file_path, "w") as f:
            json.dump({"file_hashes": current_file_hashes, "folder_hash": current_folder_hash}, f, indent=4)
    except Exception as e:
        print(f"업데이트된 해시 정보 파일 쓰기 오류: {json_hash_file_path} - {str(e)}")
        # 쓰기 오류는 해시 계산 실패로 간주하지 않음 (다음 실행 시 다시 계산)

    # 폴더 해시가 이전과 동일하고 변경된 파일이 감지되지 않았으면 이전 해시 반환
    if current_folder_hash == previous_folder_hash and not changed_files_detected[0]:
         print(f"폴더 해시 변경 없음: {folder_path}")
         return previous_folder_hash # 변경 없음을 알리기 위해 이전 해시 반환

    return current_folder_hash # 변경되었거나 첫 실행인 경우 새 해시 반환


def get_legal_cases():
    """모든 법률 사건 폴더 목록을 가져옵니다."""
    all_case_folders = []

    for legal_folder in LEGAL_FOLDERS:
        legal_folder_path = os.path.join(VAULT_PATH, legal_folder)

        try:
            if os.path.exists(legal_folder_path):
                entries = [
                    entry
                    for entry in os.listdir(legal_folder_path)
                    if os.path.isdir(os.path.join(legal_folder_path, entry))
                ]

                case_folders = [
                    {
                        "name": entry,
                        "path": os.path.join(legal_folder, entry),
                        "parentFolder": legal_folder,
                    }
                    for entry in entries
                ]

                # "INBOX" 폴더 제외 (사건 폴더의 전체 상대 경로에 "INBOX"가 포함된 경우)
                filtered_case_folders = [
                    case for case in case_folders if "INBOX" not in case["path"]
                ]
                all_case_folders.extend(filtered_case_folders)
        except Exception as e:
            print(f"폴더 접근 오류: {legal_folder_path} - {str(e)}")

    # 결과 정렬 (부모 폴더별로 그룹화)
    all_case_folders.sort(key=lambda x: (x["parentFolder"], x["name"]))

    return all_case_folders

def pack_legal_case(case_path):
    """사건 폴더를 패키징합니다."""
    case_name = os.path.basename(case_path)
    parent_folder = os.path.basename(os.path.dirname(case_path))
    # 패키징 파일 이름 생성 (타임스탬프 제거)
    # 해시 파일 이름 생성 로직과 동일하게 사건 폴더 이름에서 마지막 숫자 패턴을 제거
    cleaned_case_name = re.sub(r'_\d+$', '', case_name)
    output_file_name = f"{parent_folder}_{cleaned_case_name}.txt"
    output_file = os.path.join(OUTPUT_PATH, output_file_name)
    full_case_path = os.path.join(VAULT_PATH, case_path)

    # 해시값 계산
    current_hash = calculate_hash(full_case_path)
    if current_hash is None:
        print(f"해시값 계산 실패: {case_path}")
        return False

    # 해시 파일 경로 설정 (.hashes 서브디렉토리에 저장)
    hashes_dir = os.path.join(OUTPUT_PATH, ".hashes")
    os.makedirs(hashes_dir, exist_ok=True) # .hashes 디렉토리 생성
    # 해시 파일 이름은 사건 폴더 이름에서 마지막 숫자 패턴을 제거하고 부모 폴더 이름과 결합하여 생성
    # 예: "사건이름_20231231" -> "사건이름"
    cleaned_case_name = re.sub(r'_\d+$', '', case_name)
    # 해시 파일 이름 변경: .hash 대신 .json 사용 (calculate_hash에서 JSON 파일 사용)
    hash_file_name = f"{parent_folder}_{cleaned_case_name}_file_hashes.json"
    hash_file_path = os.path.join(hashes_dir, hash_file_name)


    # 이전 해시값 읽기 (JSON 파일에서 폴더 해시 읽기)
    previous_hash = None
    if os.path.exists(hash_file_path):
        try:
            with open(hash_file_path, "r") as f:
                data = json.load(f)
                previous_hash = data.get("folder_hash")
        except Exception as e:
            print(f"이전 해시 정보 파일 읽기 오류: {hash_file_path} - {str(e)}")
            previous_hash = None


    # 해시값 비교
    if current_hash == previous_hash:
        print(f"변경 사항 없음: {case_path}")
        return True

    # 백업 폴더 생성
    backup_path = os.path.join(
        os.path.dirname(OUTPUT_PATH), os.path.basename(OUTPUT_PATH) + BACKUP_FOLDER_NAME
    )
    os.makedirs(backup_path, exist_ok=True)

    # 기존 파일 확인 및 백업
    # 타임스탬프 없이 생성될 패키징 파일 이름을 기준으로 찾습니다.
    existing_files = [f for f in os.listdir(OUTPUT_PATH) if f == output_file_name]
    for existing_file in existing_files:
        existing_file_path = os.path.join(OUTPUT_PATH, existing_file)
        # 백업 파일 이름에 타임스탬프 추가
        seoul_timezone = pytz.timezone("Asia/Seoul")
        now = datetime.now(seoul_timezone)
        timestamp = now.strftime("%Y%m%d%H%M")
        backup_file_name = f"{os.path.splitext(existing_file)[0]}_{timestamp}.txt"
        backup_file_path = os.path.join(backup_path, backup_file_name)

        print(f"기존 파일 백업: {existing_file_path} -> {backup_file_path}")
        try:
            os.rename(existing_file_path, backup_file_path)
        except Exception as e:
            print(f"파일 이동 오류: {existing_file_path} -> {backup_file_path} - {str(e)}")
            return False

    # Repomix 실행
    try:
        print(f"사건 폴더 압축 중: {case_path}")
        command = [
            "node",
            REPOMIX_PATH,
            "-o",
            output_file,
            "--style",
            "plain",
            "--exclude",
            ".hashes",
            full_case_path,
        ]
        subprocess.run(command, check=True)
        print(f"압축 완료: {output_file}")

        # 현재 해시값 저장 (calculate_hash 함수에서 이미 JSON 파일에 저장함)
        # 이 부분은 더 이상 필요 없음
        # try:
        #     with open(hash_file_path, "w") as f:
        #         f.write(current_hash)
        # except Exception as e:
        #     print(f"현재 해시값 파일 쓰기 오류: {hash_file_path} - {str(e)}")

        return True
    except subprocess.CalledProcessError as e:
        print(f"오류 발생: {str(e)}")
        return False
    except Exception as e:
        print(f"예상치 못한 오류: {str(e)}")
        return False

def main():
    """메인 함수"""
    print("법률 사건 폴더 자동 패키징 도구")
    print("=========================")

    time.sleep(5) # 5초 지연 추가

    # 출력 디렉토리 생성
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # 사건 폴더 목록 가져오기
    legal_cases = get_legal_cases()

    # 모든 사건 폴더 패키징 (병렬 처리)
    # 시스템의 CPU 코어 수를 사용하여 풀 생성
    with multiprocessing.Pool() as pool:
        results = pool.map(pack_legal_case, [case["path"] for case in legal_cases])

    # 결과 출력 (선택 사항)
    # for i, case in enumerate(legal_cases):
    #     if results[i]:
    #         print(f"패키징 완료: {case['path']}")
    #     else:
    #         print(f"패키징 실패: {case['path']}")
    #     print("-------------------------")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {str(e)}")