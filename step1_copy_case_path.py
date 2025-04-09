import os
import pyperclip
import sys

def list_and_copy_folder_path(target_dir):
    """
    지정된 디렉토리의 하위 폴더 목록을 보여주고, 사용자가 선택한 폴더의
    전체 경로를 클립보드에 복사합니다.
    """
    # 대상 디렉토리가 실제로 존재하는지 확인
    if not os.path.isdir(target_dir):
        print(f"오류: 디렉토리를 찾을 수 없습니다 - {target_dir}")
        # input("엔터 키를 누르면 종료합니다...") # 오류 시 바로 종료하도록 변경
        sys.exit(1) # 오류 코드를 반환하며 종료

    try:
        # 하위 항목 중 디렉토리만 필터링
        subdirs = [d for d in os.listdir(target_dir) if os.path.isdir(os.path.join(target_dir, d))]
        subdirs.sort() # 가나다 순으로 정렬하여 일관성 유지

        if not subdirs:
            print(f"'{target_dir}' 디렉토리에 하위 폴더가 없습니다.")
            # input("엔터 키를 누르면 종료합니다...") # 폴더 없을 시 바로 종료
            return # 함수 종료

        print("------------------------------------")
        print("사건 폴더 목록:")
        print("------------------------------------")
        for i, dirname in enumerate(subdirs):
            print(f"{i + 1: >3}. {dirname}") # 번호 정렬 개선
        print("------------------------------------")

        while True:
            try:
                choice = input(f"클립보드에 복사할 폴더 번호 (1-{len(subdirs)}) 또는 취소(c)를 입력하세요: ")
                if choice.lower() == 'c':
                    print("작업을 취소했습니다.")
                    return # 함수 종료

                choice_num = int(choice)
                if 1 <= choice_num <= len(subdirs):
                    selected_dir_name = subdirs[choice_num - 1]
                    full_path = os.path.join(target_dir, selected_dir_name)

                    # pyperclip 예외 처리 추가
                    try:
                        pyperclip.copy(full_path)
                        print(f"\n✅ 성공: '{full_path}' 경로가 클립보드에 복사되었습니다.")
                    except pyperclip.PyperclipException as clip_err:
                        print(f"\n❌ 오류: 클립보드 복사 중 문제가 발생했습니다. 에러: {clip_err}")
                        print("수동으로 경로를 복사하세요:")
                        print(full_path)
                    break # 성공적으로 복사 후 루프 종료
                else:
                    print(f"❌ 잘못된 번호입니다. 1부터 {len(subdirs)} 사이의 번호를 입력하거나 'c'를 입력하세요.")
            except ValueError:
                print("❌ 잘못된 입력입니다. 숫자 또는 'c'를 입력하세요.")
            # 예상치 못한 오류 처리 추가
            except Exception as e:
                print(f"\n❌ 예상치 못한 오류 발생: {e}")
                sys.exit(1) # 심각한 오류 시 종료

    except FileNotFoundError:
        # 이 오류는 isdir() 체크로 인해 발생 가능성이 낮지만, 방어적으로 추가
        print(f"오류: 디렉토리를 찾는 중 문제가 발생했습니다 - {target_dir}")
        sys.exit(1)
    except PermissionError:
        print(f"오류: '{target_dir}' 디렉토리에 접근할 권한이 없습니다.")
        sys.exit(1)
    except Exception as e: # 포괄적인 오류 처리
        print(f"알 수 없는 오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # 대상 디렉토리 경로 설정 (Raw string 사용 권장)
    case_folder_path = r"F:\\내 드라이브\\LifewithAI@20250120\\Legalcases"
    list_and_copy_folder_path(case_folder_path)

    # 사용자가 결과를 확인하고 종료할 수 있도록 input() 유지
    # 단, 오류 발생 시에는 sys.exit()로 즉시 종료되므로 이 부분은 실행되지 않음
    print("\n------------------------------------")
    input("엔터 키를 누르면 프로그램을 종료합니다...")
