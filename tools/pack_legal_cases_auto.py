# pack_legal_cases_auto.py
import os
import sys
import subprocess
import json
import hashlib
from datetime import datetime
import pytz
import time
import logging
import logging.handlers
import shutil

# 설정
VAULT_PATH = r"D:\\GoogleDriveStreaming\\내 드라이브\\LifewithAI-20250120"
OUTPUT_PATH = r"D:\\GoogleDriveStreaming\\내 드라이브\\LifewithAI-20250120\\Legalcases_repomix"

# 시스템 폴더 경로
SYSTEM_FOLDER = os.path.join(OUTPUT_PATH, "_system")
CACHE_PATH = os.path.join(SYSTEM_FOLDER, "metadata_cache.json")
LOG_PATH = os.path.join(SYSTEM_FOLDER, "logs", "packaging_log.txt")

# 법률 폴더 목록
LEGAL_FOLDERS = [
    '1100_Legaladvises',
    '1200_Legalcases',
    '1300_Legalcases_(주)대구농산',
    '1400_Legalcases_(주)리하온'
]

# 패키징 제외 폴더 패턴 (대소문자 구분 없이)
EXCLUDE_PATTERNS = ["_inbox", "inbox", "legalcases_repomix"]

# 로그 관리 설정
MAX_LOG_SIZE = 5 * 1024 * 1024  # 최대 로그 파일 크기 (5MB)
LOG_BACKUP_COUNT = 5            # 유지할 백업 로그 파일 수

# 로거 초기화 (실제 설정은 나중에)
logger = None

# 로깅 설정 함수
def setup_logging():
    """로깅을 설정합니다."""
    # 로그 디렉토리 생성
    log_dir = os.path.dirname(LOG_PATH)
    os.makedirs(log_dir, exist_ok=True)
    
    # 로그 파일 이름에 날짜 추가
    today = datetime.now(pytz.timezone('Asia/Seoul')).strftime("%Y%m%d")
    log_file = os.path.join(log_dir, f"packaging_log_{today}.txt")
    
    # 로거 생성
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    
    # 포맷터 생성
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # 파일 핸들러 (로그 로테이션 적용)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, 
        maxBytes=MAX_LOG_SIZE, 
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 기존 핸들러 제거 (중복 방지)
    if logger.handlers:
        logger.handlers.clear()
        
    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_folder_metadata(folder_path):
    """
    폴더의 메타데이터를 계산합니다.
    
    Args:
        folder_path: 메타데이터를 계산할 폴더 경로
        
    Returns:
        dict: 폴더 메타데이터 (최종 수정 시간, 파일 개수, 총 크기, 간단한 해시값)
    """
    if not os.path.exists(folder_path):
        logger.warning(f"존재하지 않는 폴더입니다: {folder_path}")
        return None
        
    metadata = {
        "last_modified": 0,
        "file_count": 0,
        "total_size": 0,
        "files_metadata": []
    }
    
    try:
        for root, dirs, files in os.walk(folder_path):
            # INBOX 관련 폴더는 스킵
            dirs[:] = [d for d in dirs if not any(pattern.lower() in d.lower() for pattern in EXCLUDE_PATTERNS)]
            
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    stats = os.stat(file_path)
                    file_mtime = stats.st_mtime
                    file_size = stats.st_size
                    
                    # 최종 수정 시간 업데이트
                    metadata["last_modified"] = max(metadata["last_modified"], file_mtime)
                    
                    # 파일 카운트 및 크기 업데이트
                    metadata["file_count"] += 1
                    metadata["total_size"] += file_size
                    
                    # 파일 메타데이터 수집 (상대 경로 저장)
                    rel_path = os.path.relpath(file_path, folder_path)
                    metadata["files_metadata"].append({
                        "path": rel_path,
                        "size": file_size,
                        "mtime": file_mtime
                    })
                except (FileNotFoundError, PermissionError) as e:
                    logger.warning(f"파일 메타데이터 접근 오류: {file_path} - {str(e)}")
                    continue
        
        # 간단한 해시 계산 (파일 경로, 크기, 수정 시간 기반)
        hash_data = json.dumps(sorted(metadata["files_metadata"], key=lambda x: x["path"]))
        metadata["folder_hash"] = hashlib.md5(hash_data.encode()).hexdigest()
        
        # 최종 수정 시간을 읽기 쉬운 형식으로 변환
        if metadata["last_modified"] > 0:
            metadata["last_modified_iso"] = datetime.fromtimestamp(
                metadata["last_modified"], pytz.timezone('Asia/Seoul')
            ).isoformat()
        else:
            metadata["last_modified_iso"] = None
            
        return metadata
    except Exception as e:
        logger.error(f"폴더 메타데이터 계산 중 오류 발생: {folder_path} - {str(e)}")
        return None

def is_folder_changed(folder_path, folder_rel_path, metadata_cache):
    """
    폴더가 변경되었는지 확인합니다.
    
    Args:
        folder_path: 실제 폴더 경로
        folder_rel_path: 캐시에 저장할 상대 경로 키
        metadata_cache: 메타데이터 캐시
        
    Returns:
        tuple: (변경 여부, 현재 메타데이터)
    """
    current_metadata = get_folder_metadata(folder_path)
    if current_metadata is None:
        return False, None
        
    # 캐시에 폴더가 없으면 변경된 것으로 처리
    if folder_rel_path not in metadata_cache["case_folders"]:
        logger.info(f"새로운 폴더 감지됨: {folder_rel_path}")
        return True, current_metadata
        
    cached_metadata = metadata_cache["case_folders"][folder_rel_path]
    
    # 해시값 비교
    if "folder_hash" in cached_metadata and "folder_hash" in current_metadata:
        if cached_metadata["folder_hash"] != current_metadata["folder_hash"]:
            logger.info(f"폴더 내용 변경 감지됨: {folder_rel_path}")
            return True, current_metadata
            
    # 파일 개수 비교
    if "file_count" in cached_metadata and "file_count" in current_metadata:
        if cached_metadata["file_count"] != current_metadata["file_count"]:
            logger.info(f"파일 개수 변경 감지됨: {folder_rel_path} ({cached_metadata['file_count']} -> {current_metadata['file_count']})")
            return True, current_metadata
            
    # 최종 수정 시간 비교
    if "last_modified" in cached_metadata and "last_modified" in current_metadata:
        if abs(cached_metadata["last_modified"] - current_metadata["last_modified"]) > 0.001:  # 작은 부동소수점 오차 허용
            logger.info(f"최종 수정 시간 변경 감지됨: {folder_rel_path}")
            return True, current_metadata
    
    # 변경 없음
    logger.info(f"변경 없음: {folder_rel_path}")
    return False, current_metadata

def load_metadata_cache():
    """
    메타데이터 캐시를 로드합니다.
    
    Returns:
        dict: 메타데이터 캐시
    """
    default_cache = {
        "last_full_run": None,
        "case_folders": {}
    }
    
    if not os.path.exists(CACHE_PATH):
        logger.info(f"메타데이터 캐시 파일이 없습니다. 새 캐시를 생성합니다: {CACHE_PATH}")
        return default_cache
        
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            cache = json.load(f)
            logger.info(f"메타데이터 캐시 로드 완료: {CACHE_PATH}")
            return cache
    except (json.JSONDecodeError, FileNotFoundError, PermissionError) as e:
        logger.warning(f"메타데이터 캐시 로드 중 오류 발생: {str(e)}")
        logger.info("새 캐시를 생성합니다...")
        return default_cache

def save_metadata_cache(cache):
    """
    메타데이터 캐시를 저장합니다.
    
    Args:
        cache: 저장할 메타데이터 캐시
    """
    # 출력 디렉토리 확인 및 생성
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    
    try:
        # 백업 파일 생성 - 기존 캐시 보존
        if os.path.exists(CACHE_PATH):
            backup_file = f"{CACHE_PATH}.bak"
            try:
                shutil.copy2(CACHE_PATH, backup_file)
                logger.info(f"메타데이터 캐시 백업 생성: {backup_file}")
            except Exception as e:
                logger.warning(f"메타데이터 캐시 백업 생성 실패: {str(e)}")
        
        # 새 캐시 저장
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
        logger.info(f"메타데이터 캐시 저장 완료: {CACHE_PATH}")
    except (PermissionError, IOError) as e:
        logger.error(f"메타데이터 캐시 저장 중 오류 발생: {str(e)}")

def get_legal_cases():
    """
    모든 법률 사건 폴더 목록을 가져옵니다.
    
    Returns:
        list: 사건 폴더 목록 (dict 형태: name, path, parentFolder)
    """
    all_case_folders = []

    for legal_folder in LEGAL_FOLDERS:
        legal_folder_path = os.path.join(VAULT_PATH, legal_folder)

        try:
            if os.path.exists(legal_folder_path):
                entries = [entry for entry in os.listdir(legal_folder_path)
                          if os.path.isdir(os.path.join(legal_folder_path, entry))]

                # 제외 패턴을 포함하는 폴더 제외 (대소문자 구분 없이)
                case_folders = [
                    {
                        "name": entry,
                        "path": os.path.join(legal_folder, entry).replace("\\", "/"),  # Windows/Unix 호환성 위해 슬래시 통일
                        "parentFolder": legal_folder
                    }
                    for entry in entries
                    if not any(pattern.lower() in entry.lower() for pattern in EXCLUDE_PATTERNS)
                ]

                all_case_folders.extend(case_folders)
        except Exception as e:
            logger.error(f"폴더 접근 오류: {legal_folder_path} - {str(e)}")

    # 결과 정렬 (부모 폴더별로 그룹화)
    all_case_folders.sort(key=lambda x: (x["parentFolder"], x["name"]))

    return all_case_folders

def pack_legal_case(case_path):
    """
    사건 폴더를 패키징합니다.
    
    Args:
        case_path: 패키징할 사건 폴더 경로
        
    Returns:
        bool: 패키징 성공 여부
    """
    # 사건 폴더 이름 추출
    case_name = os.path.basename(case_path)
    
    # 제외 패턴 체크
    for pattern in EXCLUDE_PATTERNS:
        if pattern.lower() in case_name.lower():
            logger.info(f"제외 패턴 '{pattern}' 포함 폴더는 패키징하지 않습니다: {case_path}")
            return False

    # 현재 날짜와 시간 (서울 시각)
    seoul_timezone = pytz.timezone('Asia/Seoul')
    now = datetime.now(seoul_timezone)
    timestamp = now.strftime("%Y%m%d%H%M")

    # 출력 파일 경로
    output_file = os.path.join(OUTPUT_PATH, f"{case_name}_{timestamp}.txt")

    # 출력 디렉토리 생성
    os.makedirs(OUTPUT_PATH, exist_ok=True)

    # 백업 디렉토리 생성
    backup_path = os.path.join(SYSTEM_FOLDER, "backups")
    os.makedirs(backup_path, exist_ok=True)

    # 기존 파일 확인 및 백업
    existing_files = [f for f in os.listdir(OUTPUT_PATH) if f.startswith(case_name) and f.endswith(".txt")]
    for existing_file in existing_files:
        existing_file_path = os.path.join(OUTPUT_PATH, existing_file)
        backup_file_path = os.path.join(backup_path, existing_file)
        logger.info(f"기존 파일 백업: {existing_file_path} -> {backup_file_path}")
        os.rename(existing_file_path, backup_file_path)

    # Repomix 실행
    try:
        logger.info(f"사건 폴더 압축 중: {case_path}")
        full_case_path = os.path.join(VAULT_PATH, case_path.replace("/", os.sep))

        # npm.cmd를 사용하여 전역 설치된 repomix 실행
        command = [
            "npm.cmd",
            "exec",
            "repomix",
            "--",  # -- 는 npm에게 이후 매개변수는 repomix에 전달하라는 의미
            "-o", output_file,
            "--style", "plain",
            full_case_path
        ]

        # 명령어 실행
        subprocess.run(command, check=True)

        logger.info(f"압축 완료: {output_file}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"압축 중 오류 발생: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"예상치 못한 오류: {str(e)}")
        return False

def batch_process_legal_cases(force_all=False):
    """
    모든 법률 사건 폴더를 자동으로 처리합니다.
    
    Args:
        force_all: 강제로 모든 폴더 재패키징 여부
        
    Returns:
        tuple: (성공 수, 실패 수, 건너뛴 수)
    """
    # 메타데이터 캐시 로드
    metadata_cache = load_metadata_cache()
    
    # 사건 폴더 목록 가져오기
    legal_cases = get_legal_cases()
    logger.info(f"{len(legal_cases)}개의 법률 사건 폴더를 찾았습니다.")
    
    # 통계
    success_count = 0
    failed_count = 0
    skipped_count = 0
    
    # 전체 시작 시간
    start_time = time.time()
    
    # 각 사건 폴더 처리
    for i, case_folder in enumerate(legal_cases):
        case_path = case_folder["path"]
        full_case_path = os.path.join(VAULT_PATH, case_path.replace("/", os.sep))
        
        logger.info(f"[{i+1}/{len(legal_cases)}] 처리 중: {case_path}")
        
        # 제외 패턴 체크
        if any(pattern.lower() in case_folder["name"].lower() for pattern in EXCLUDE_PATTERNS):
            logger.info(f"제외 패턴 포함 폴더 건너뛰기: {case_path}")
            skipped_count += 1
            continue
        
        # 강제 패키징 또는 변경 감지
        if force_all:
            should_package = True
            logger.info(f"강제 패키징: {case_path}")
        else:
            # 변경 감지
            should_package, current_metadata = is_folder_changed(
                full_case_path, case_path, metadata_cache
            )
            
            # 메타데이터 업데이트
            if current_metadata:
                metadata_cache["case_folders"][case_path] = current_metadata
        
        # 패키징 필요 시 실행
        if should_package:
            success = pack_legal_case(case_path)
            if success:
                success_count += 1
                # 패키징 시간 업데이트
                if case_path in metadata_cache["case_folders"]:
                    metadata_cache["case_folders"][case_path]["last_packaged"] = datetime.now(
                        pytz.timezone('Asia/Seoul')
                    ).isoformat()
            else:
                failed_count += 1
        else:
            logger.info(f"변경 없음, 패키징 건너뜀: {case_path}")
            skipped_count += 1
        
        # 주기적으로 캐시 저장 (10개 처리마다 또는 마지막)
        if (i + 1) % 10 == 0 or i == len(legal_cases) - 1:
            save_metadata_cache(metadata_cache)
    
    # 실행 완료 통계
    end_time = time.time()
    elapsed_time = end_time - start_time
    
    # 최종 실행 시간 업데이트
    metadata_cache["last_full_run"] = datetime.now(pytz.timezone('Asia/Seoul')).isoformat()
    save_metadata_cache(metadata_cache)
    
    logger.info(f"처리 완료: 총 {len(legal_cases)}개 폴더 중 {success_count}개 성공, {failed_count}개 실패, {skipped_count}개 건너뜀")
    logger.info(f"소요 시간: {elapsed_time:.2f}초")
    
    return success_count, failed_count, skipped_count

def main():
    """메인 함수"""
    # 전역 로거 사용
    global logger
    if logger is None:
        logger = setup_logging()
    
    logger.info("법률 사건 폴더 자동 패키징 도구 v1.2")
    logger.info("==================================")
    logger.info(f"출력 경로: {OUTPUT_PATH}")
    logger.info(f"시스템 폴더: {SYSTEM_FOLDER}")
    logger.info(f"로그 폴더: {os.path.dirname(LOG_PATH)}")
    logger.info(f"메타데이터 캐시: {CACHE_PATH}")
    logger.info(f"패키징 제외 패턴: {EXCLUDE_PATTERNS}")
    logger.info(f"로그 설정: 최대 크기 {MAX_LOG_SIZE/1024/1024:.1f}MB, 백업 파일 {LOG_BACKUP_COUNT}개")
    
    # 실행 모드 선택
    print("\n실행 모드를 선택하세요:")
    print("1. 자동 모드 (변경된 폴더만 패키징)")
    print("2. 전체 강제 패키징 모드 (모든 폴더 재패키징)")
    print("3. 인터랙티브 모드 (개별 폴더 선택)")
    
    try:
        mode = input("모드 선택 (1-3, 기본값: 1): ").strip() or "1"
        
        if mode == "1":
            logger.info("자동 모드 시작: 변경된 폴더만 패키징")
            success_count, failed_count, skipped_count = batch_process_legal_cases(force_all=False)
            
            print(f"\n처리 완료: 총 {success_count + failed_count + skipped_count}개 폴더")
            print(f"- 성공: {success_count}개")
            print(f"- 실패: {failed_count}개")
            print(f"- 변경 없음: {skipped_count}개")
            
        elif mode == "2":
            logger.info("전체 강제 패키징 모드 시작: 모든 폴더 재패키징")
            success_count, failed_count, skipped_count = batch_process_legal_cases(force_all=True)
            
            print(f"\n처리 완료: 총 {success_count + failed_count + skipped_count}개 폴더")
            print(f"- 성공: {success_count}개")
            print(f"- 실패: {failed_count}개")
            print(f"- 건너뜀: {skipped_count}개")
            
        elif mode == "3":
            # 인터랙티브 모드
            logger.info("인터랙티브 모드 시작: 개별 폴더 선택")
            
            # 기존 코드의 인터랙티브 로직 활용
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
                # 한 자리 수일 경우 앞에 0을 붙여 두 자리로 표시
                index_str = f"{i + 1:02d}"
                print(f"{index_str}. {case_folder['name']}")

            # 메타데이터 캐시 로드
            metadata_cache = load_metadata_cache()

            # 폴더별 변경 상태 표시
            print("\n폴더 변경 상태:")
            for i, case_folder in enumerate(legal_cases):
                case_path = case_folder["path"]
                full_path = os.path.join(VAULT_PATH, case_path.replace("/", os.sep))
                
                # 변경 확인
                changed, _ = is_folder_changed(full_path, case_path, metadata_cache)
                status = "변경됨 *" if changed else "변경 없음"
                
                # 인덱스와 상태 표시
                index_str = f"{i + 1:02d}"
                print(f"{index_str}. {case_folder['name']} - {status}")

            # 사용자 입력 받기
            answer = input("\n패키징할 사건 폴더의 번호 또는 경로를 입력하세요 (쉼표로 구분하여 여러 개 선택 가능): ")

            # 쉼표로 구분된 입력 처리
            selected_items = [item.strip() for item in answer.split(",")]
            
            for item in selected_items:
                case_path = ""
                
                # 번호로 입력한 경우
                if item.isdigit():
                    index = int(item) - 1
                    if 0 <= index < len(legal_cases):
                        case_path = legal_cases[index]["path"]
                    else:
                        print(f"잘못된 번호입니다: {item}")
                        continue
                # 경로로 입력한 경우
                else:
                    case_path = item
                    
                    # 경로가 존재하는지 확인
                    full_path = os.path.join(VAULT_PATH, case_path.replace("/", os.sep))
                    if not os.path.exists(full_path):
                        print(f"경로를 찾을 수 없습니다: {full_path}")
                        continue

                # 패키징 실행
                print(f"\n'{case_path}' 패키징 중...")
                success = pack_legal_case(case_path)

                # 성공 시 메타데이터 업데이트
                if success:
                    print("패키징 성공!")
                    # 메타데이터 갱신
                    full_path = os.path.join(VAULT_PATH, case_path.replace("/", os.sep))
                    new_metadata = get_folder_metadata(full_path)
                    if new_metadata:
                        metadata_cache["case_folders"][case_path] = new_metadata
                        metadata_cache["case_folders"][case_path]["last_packaged"] = datetime.now(
                            pytz.timezone('Asia/Seoul')
                        ).isoformat()
                else:
                    print("패키징 실패.")
            
            # 최종 메타데이터 저장
            save_metadata_cache(metadata_cache)
            
        else:
            print("잘못된 모드 선택. 자동 모드로 실행합니다.")
            batch_process_legal_cases(force_all=False)
            
    except KeyboardInterrupt:
        logger.warning("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 실행 중 오류 발생: {str(e)}")
    finally:
        logger.info("프로그램 종료")

if __name__ == "__main__":
    # 시작 전 디렉토리 확인 및 생성
    os.makedirs(OUTPUT_PATH, exist_ok=True)
    os.makedirs(SYSTEM_FOLDER, exist_ok=True)
    
    # 로깅 설정
    logger = setup_logging()
    
    try:
        main()
    except KeyboardInterrupt:
        logger.warning("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"프로그램 실행 중 예상치 못한 오류 발생: {str(e)}")
        # 예외 상세 정보 출력
        import traceback
        logger.error(f"상세 오류 정보:\n{traceback.format_exc()}")