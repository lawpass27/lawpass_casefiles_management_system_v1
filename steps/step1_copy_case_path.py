import os
import sys

# 통합 플랫폼 유틸리티 사용
try:
    from utils.platform_utils import get_platform_manager, convert_path
    platform_manager = get_platform_manager()
except ImportError:
    # 기존 방식 fallback (호환성)
    import platform
    import subprocess
    
    def get_cross_platform_path(windows_path):
        """레거시 경로 변환 함수 (fallback)"""
        system = platform.system()
        is_wsl = 'microsoft' in platform.uname().release.lower() or 'WSL' in platform.uname().release
        
        if system == "Linux" and is_wsl:
            if windows_path.startswith("D:\\"):
                return windows_path.replace("D:\\", "/mnt/d/").replace("\\", "/")
            elif windows_path.startswith("C:\\"):
                return windows_path.replace("C:\\", "/mnt/c/").replace("\\", "/")
            else:
                drive_letter = windows_path[0].lower()
                return windows_path.replace(f"{windows_path[0]}:\\", f"/mnt/{drive_letter}/").replace("\\", "/")
        else:
            return windows_path
    
    convert_path = get_cross_platform_path
    platform_manager = None

# 설정
VAULT_PATH = convert_path("D:\\GoogleDriveLaptop\\LifewithAI-20250120")

# 법률 폴더 목록
LEGAL_FOLDERS = [
    '1100_Legaladvises',
    '1200_Legalcases',
    '1300_Legalcases_(주)대구농산',
    '1400_Legalcases_(주)리하온'
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

                # _INBOX 폴더 제외 (대소문자 구분 없이)
                case_folders = [
                    {
                        "name": entry,
                        "path": os.path.join(legal_folder, entry),
                        "parentFolder": legal_folder
                    }
                    for entry in entries
                    if "_inbox" not in entry.lower()  # 대소문자 구분 없이 _inbox가 포함되지 않은 항목만 포함
                ]

                all_case_folders.extend(case_folders)
        except Exception as e:
            print(f"폴더 접근 오류: {legal_folder_path} - {str(e)}")

    # 결과 정렬 (부모 폴더별로 그룹화)
    all_case_folders.sort(key=lambda x: (x["parentFolder"], x["name"]))

    return all_case_folders

def list_and_copy_folder_path(parent_dirs=None):
    """
    사건 폴더 목록을 보여주고, 사용자가 선택한 폴더의
    전체 경로를 클립보드에 복사하고 case_path.txt 파일에 저장합니다.
    """
    try:
        # 사건 폴더 목록 가져오기
        legal_cases = get_legal_cases()

        if not legal_cases:
            print("지정된 디렉토리에 사건 폴더가 없습니다.")
            return # 함수 종료

        print("=====================================")
        print("법률 사건 목록")
        print("=====================================")
        
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
        print("------------------------------------")

        # 사용자 입력 받기
        answer = input("\n클립보드에 복사할 사건 폴더의 번호 또는 경로를 입력하세요: ")

        case_path = ""
        full_path = ""

        # 번호로 입력한 경우
        if answer.isdigit():
            index = int(answer) - 1
            if 0 <= index < len(legal_cases):
                case_folder = legal_cases[index]
                case_path = case_folder["path"]
                full_path = os.path.join(VAULT_PATH, case_path)
                print(f"\n선택: [{case_folder['parentFolder']}] {case_folder['name']}")
            else:
                print("잘못된 번호입니다.")
                return
        # 경로로 입력한 경우
        else:
            case_path = answer
            full_path = os.path.join(VAULT_PATH, case_path)
            
            # 경로가 존재하는지 확인
            if not os.path.exists(full_path):
                print(f"경로를 찾을 수 없습니다: {full_path}")
                return

        # 크로스플랫폼 클립보드 복사
        try:
            if platform_manager:
                # 새로운 플랫폼 매니저 사용
                clipboard_success = platform_manager.cmd.copy_to_clipboard(full_path)
            else:
                # 기존 방식 fallback
                clipboard_success = False
                system = platform.system()
                is_wsl = 'microsoft' in platform.uname().release.lower() or 'WSL' in platform.uname().release
                
                if system == "Linux" and is_wsl:
                    subprocess.run(['clip.exe'], input=full_path.encode('utf-8'), check=True)
                    clipboard_success = True
                elif system == "Windows":
                    subprocess.run(['clip'], input=full_path.encode('utf-8'), check=True)
                    clipboard_success = True
                elif system == "Darwin":
                    subprocess.run(['pbcopy'], input=full_path.encode('utf-8'), check=True)
                    clipboard_success = True
                elif system == "Linux":
                    try:
                        subprocess.run(['xclip', '-selection', 'clipboard'], input=full_path.encode('utf-8'), check=True)
                        clipboard_success = True
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        try:
                            subprocess.run(['xsel', '--clipboard', '--input'], input=full_path.encode('utf-8'), check=True)
                            clipboard_success = True
                        except (subprocess.CalledProcessError, FileNotFoundError):
                            pass
            
            if clipboard_success:
                print(f"\n✅ 성공: {full_path} 경로가 클립보드에 복사되었습니다.")
            else:
                print(f"\n⚠️  경고: 클립보드 복사가 지원되지 않는 환경입니다.")
                print("수동으로 경로를 복사하세요:")
                print(full_path)
                
        except Exception as e:
            print(f"\n❌ 오류: 클립보드 복사 중 문제가 발생했습니다. 에러: {e}")
            print("수동으로 경로를 복사하세요:")
            print(full_path)

        # 파일에 경로 저장
        try:
            with open("case_path.txt", "w", encoding="utf-8") as f:
                f.write(full_path)
            print(f"✅ 성공: {full_path} 경로가 case_path.txt 파일에 저장되었습니다.")
        except Exception as save_err:
            print(f"❌ 오류: 경로를 파일에 저장하는 중 문제가 발생했습니다. 에러: {save_err}")
            print("프로그램이 계속 진행되지만, 다음 단계에서 문제가 발생할 수 있습니다.")

    except FileNotFoundError:
        # 이 오류는 isdir() 체크로 인해 발생 가능성이 낮지만, 방어적으로 추가
        print(f"오류: 디렉토리를 찾는 중 문제가 발생했습니다")
        sys.exit(1)
    except PermissionError:
        print(f"오류: 디렉토리에 접근할 권한이 없습니다.")
        sys.exit(1)
    except Exception as e: # 포괄적인 오류 처리
        print(f"알 수 없는 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        list_and_copy_folder_path()
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"프로그램 실행 중 오류 발생: {str(e)}")
    finally:
        # 사용자가 결과를 확인하고 종료할 수 있도록 input() 유지
        print("\n------------------------------------")
        input("엔터 키를 누르면 프로그램을 종료합니다...")

