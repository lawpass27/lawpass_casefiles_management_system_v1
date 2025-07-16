# -*- coding: utf-8 -*-
"""
전자소송 파일 복사 및 백업 모듈
"""
import os
import sys
import time
import shutil
import argparse
import yaml
import platform
from datetime import datetime

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

def get_timestamp():
    """타임스탬프 생성"""
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def copy_file_with_chunks(src, dst, chunk_size=1024*1024):
    """
    청크 단위로 파일 복사 (대용량 파일 처리용)
    
    Args:
        src: 소스 파일 경로
        dst: 대상 파일 경로
        chunk_size: 청크 크기 (기본값: 1MB)
    """
    # 디렉토리 생성
    dst_dir = os.path.dirname(dst)
    if not os.path.exists(dst_dir):
        os.makedirs(dst_dir)
    
    # 청크 단위로 파일 복사
    with open(src, 'rb') as fsrc:
        with open(dst, 'wb') as fdst:
            while True:
                chunk = fsrc.read(chunk_size)
                if not chunk:
                    break
                fdst.write(chunk)

def copy_and_backup_files(source_folder, case_folder, backup_folder, original_folder_name="원본폴더", chunk_size=1024*1024):
    """
    전자소송 다운로드 폴더에서 사건 폴더로 파일 복사 및 백업
    
    Args:
        source_folder: 소스 폴더 경로 (전자소송 다운로드 폴더)
        case_folder: 사건 폴더 경로
        backup_folder: 백업 폴더 경로
        original_folder_name: 원본 폴더명 (기본값: '원본폴더')
        chunk_size: 파일 복사 시 청크 크기 (기본값: 1MB)
        
    Returns:
        (복사된 파일 수, 백업된 파일 수, 오류 메시지 목록)
    """
    # 폴더 존재 여부 확인 및 생성
    if not os.path.exists(source_folder) or not os.path.isdir(source_folder):
        return 0, 0, [f"소스 폴더가 존재하지 않거나 폴더가 아닙니다: {source_folder}"]
    
    if not os.path.exists(case_folder):
        try:
            os.makedirs(case_folder)
            print(f"사건 폴더 생성 완료: {case_folder}")
        except Exception as e:
            return 0, 0, [f"사건 폴더 생성 실패: {e}"]
    
    # 원본 폴더 경로 생성
    original_folder_path = os.path.join(case_folder, original_folder_name)
    if not os.path.exists(original_folder_path):
        try:
            os.makedirs(original_folder_path)
            print(f"원본 폴더 생성 완료: {original_folder_path}")
        except Exception as e:
            return 0, 0, [f"원본 폴더 생성 실패: {e}"]
    
    # 사건 폴더 이름 추출
    case_folder_name = os.path.basename(os.path.normpath(case_folder))
    
    # 백업 폴더 내에 사건 폴더명_백업 폴더 생성
    case_backup_folder_name = f"{case_folder_name}_백업"
    case_backup_folder_path = os.path.join(backup_folder, case_backup_folder_name)
    
    if not os.path.exists(case_backup_folder_path):
        try:
            os.makedirs(case_backup_folder_path)
            print(f"사건 백업 폴더 생성 완료: {case_backup_folder_path}")
        except Exception as e:
            return 0, 0, [f"사건 백업 폴더 생성 실패: {e}"]
    
    # 파일 복사 및 백업 처리
    copied_count = 0
    backed_up_count = 0
    errors = []
    
    # 소스 폴더의 모든 파일 목록 가져오기
    try:
        file_list = [f for f in os.listdir(source_folder) if os.path.isfile(os.path.join(source_folder, f))]
    except Exception as e:
        return 0, 0, [f"소스 폴더 파일 목록 가져오기 실패: {e}"]
    
    total_files = len(file_list)
    print(f"처리할 파일 수: {total_files}")
    
    for idx, filename in enumerate(file_list, 1):
        source_path = os.path.join(source_folder, filename)
        target_path = os.path.join(original_folder_path, filename)
        
        # 진행 상황 출력
        if idx % 5 == 0 or idx == total_files:
            print(f"진행 상황: {idx}/{total_files} ({idx/total_files*100:.1f}%)")
        
        # 이미 존재하는 파일 처리
        if os.path.exists(target_path):
            # 백업 파일명 생성 (파일명_YYYYMMDD_HHMMSS.확장자)
            timestamp = get_timestamp()
            name, ext = os.path.splitext(filename)
            backup_filename = f"{name}_{timestamp}{ext}"
            backup_path = os.path.join(original_folder_path, backup_filename)
            
            try:
                # 청크 단위로 파일 복사
                copy_file_with_chunks(target_path, backup_path, chunk_size)
                backed_up_count += 1
                print(f"파일 백업 완료: {backup_path}")
            except Exception as e:
                errors.append(f"파일 백업 실패 ({filename}): {e}")
                continue
        
        # 파일 복사
        try:
            # 청크 단위로 파일 복사
            copy_file_with_chunks(source_path, target_path, chunk_size)
            copied_count += 1
            print(f"파일 복사 완료: {target_path}")
            
            # 원본 파일을 사건 백업 폴더로 이동
            backup_path = os.path.join(case_backup_folder_path, filename)
            if os.path.exists(backup_path):
                # 백업 폴더에 이미 파일이 있으면 타임스탬프 추가
                timestamp = get_timestamp()
                name, ext = os.path.splitext(filename)
                backup_filename = f"{name}_{timestamp}{ext}"
                backup_path = os.path.join(case_backup_folder_path, backup_filename)
            
            # 파일 이동 (대용량 파일은 복사 후 삭제)
            if os.path.getsize(source_path) > 100 * 1024 * 1024:  # 100MB 이상
                copy_file_with_chunks(source_path, backup_path, chunk_size)
                os.remove(source_path)
            else:
                shutil.move(source_path, backup_path)
                
            print(f"원본 파일 사건 백업 폴더로 이동 완료: {backup_path}")
            
        except Exception as e:
            errors.append(f"파일 복사 실패 ({filename}): {e}")
            # 오류 발생 시 잠시 대기 후 계속 진행
            time.sleep(1)
    
    return copied_count, backed_up_count, errors

def get_case_folder():
    """사용자에게 사건 폴더 경로 입력 받기"""
    # 먼저 case_path.txt 파일에서 경로 읽기 시도
    if os.path.exists("case_path.txt"):
        try:
            with open("case_path.txt", "r", encoding="utf-8") as f:
                saved_path = f.read().strip()
                if saved_path:
                    use_saved = input(f"\ncase_path.txt에 저장된 경로: {saved_path}\n이 경로를 사용하시겠습니까? (y/n, 기본값: y): ").lower() or 'y'
                    if use_saved == 'y':
                        return saved_path
        except Exception as e:
            print(f"case_path.txt 파일 읽기 오류: {e}")
    
    # 저장된 경로가 없거나 사용하지 않는 경우 새로 입력 받기
    case_folder = input("사건 폴더 경로를 입력하세요: ")
    # 따옴표 제거
    case_folder = case_folder.strip('"\'')
    return os.path.normpath(case_folder)

def main():
    parser = argparse.ArgumentParser(description='전자소송 파일 복사 및 백업')
    parser.add_argument('case_folder', nargs='?', help='사건 폴더 경로')
    parser.add_argument('--source', '-s', help='전자소송 다운로드 폴더 경로')
    parser.add_argument('--backup', '-b', help='백업 폴더 경로')
    parser.add_argument('--original-folder', '-o', help='원본 폴더명')
    parser.add_argument('--config', help='설정 파일 경로')
    parser.add_argument('--chunk-size', type=int, default=1024*1024, help='파일 복사 청크 크기 (바이트)')
    
    args = parser.parse_args()
    
    # 설정 파일 경로
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = args.config or os.path.join(script_dir, 'config.yaml')
    
    # 설정 파일 로드
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                
            # 설정 파일에서 값 가져오기
            source_folder = args.source or config.get('general', {}).get('source_folder', 'D:\\전자소송다운로드')
            case_folder = args.case_folder or config.get('general', {}).get('case_folder', '')
            backup_folder = args.backup or config.get('general', {}).get('backup_folder', 'D:\\전자소송다운로드_백업')
            original_folder_name = args.original_folder or config.get('file_management', {}).get('original_folder_name', '원본폴더')
            
            # Windows 경로를 크로스플랫폼 경로로 변환
            if source_folder and '\\' in source_folder:
                source_folder = get_cross_platform_path(source_folder)
            if backup_folder and '\\' in backup_folder:
                backup_folder = get_cross_platform_path(backup_folder)
        except Exception as e:
            print(f"설정 파일 로드 실패: {e}")
            return 1
    else:
        source_folder = args.source or get_cross_platform_path('D:\\전자소송다운로드')
        case_folder = args.case_folder
        backup_folder = args.backup or get_cross_platform_path('D:\\전자소송다운로드_백업')
        original_folder_name = args.original_folder or '원본폴더'
    
    # 필수 인자 확인
    if not source_folder:
        print("소스 폴더 경로를 지정해야 합니다.")
        return 1
    
    if not case_folder:
        # 사용자에게 사건 폴더 경로 입력 받기
        print("사건 폴더 경로가 지정되지 않았습니다.")
        case_folder = get_case_folder()
        
        if not case_folder:
            print("사건 폴더 경로를 지정해야 합니다.")
            return 1
    
    # Windows 경로를 크로스플랫폼 경로로 변환 (필요한 경우)
    if case_folder and '\\' in case_folder:
        case_folder = get_cross_platform_path(case_folder)
    
    # 경로 정규화
    source_folder = os.path.normpath(source_folder)
    case_folder = os.path.normpath(case_folder)
    backup_folder = os.path.normpath(backup_folder)
    
    # 파일 복사 및 백업 실행
    try:
        copied_count, backed_up_count, errors = copy_and_backup_files(
            source_folder, case_folder, backup_folder, original_folder_name, args.chunk_size
        )
        
        # 결과 출력
        print(f"\n처리 완료:")
        print(f"- 복사된 파일 수: {copied_count}")
        print(f"- 백업된 파일 수: {backed_up_count}")
        
        if errors:
            print("\n오류 목록:")
            for error in errors:
                print(f"- {error}")
            return 1
        
        return 0
    except Exception as e:
        print(f"예기치 않은 오류 발생: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())