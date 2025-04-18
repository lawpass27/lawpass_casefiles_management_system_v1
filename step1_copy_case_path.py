import os
import pyperclip
import sys

def get_subfolders_from_multiple_dirs(parent_dirs):
    """
    여러 부모 디렉토리에서 모든 하위 폴더를 수집합니다.
    각 하위 폴더에 대해 (부모 디렉토리, 하위 폴더 이름, 전체 경로)를 반환합니다.
    """
    all_subfolders = []

    for parent_dir in parent_dirs:
        # 디렉토리가 존재하는지 확인
        if not os.path.isdir(parent_dir):
            print(f"경고: 디렉토리를 찾을 수 없습니다 - {parent_dir}")
            continue

        try:
            # 하위 항목 중 디렉토리만 필터링
            subdirs = [d for d in os.listdir(parent_dir) if os.path.isdir(os.path.join(parent_dir, d))]

            # 각 하위 폴더에 대한 정보 저장
            for subdir in subdirs:
                full_path = os.path.join(parent_dir, subdir)
                # 부모 디렉토리 이름 추출 (마지막 폴더 이름만)
                parent_name = os.path.basename(parent_dir)
                all_subfolders.append((parent_name, subdir, full_path))

        except Exception as e:
            print(f"경고: '{parent_dir}' 디렉토리 처리 중 오류 발생: {e}")

    # 하위 폴더 이름으로 정렬
    all_subfolders.sort(key=lambda x: x[1])
    return all_subfolders

def list_and_copy_folder_path(parent_dirs):
    """
    여러 부모 디렉토리의 하위 폴더 목록을 보여주고, 사용자가 선택한 폴더의
    전체 경로를 클립보드에 복사하고 case_path.txt 파일에 저장합니다.
    """
    try:
        # 여러 부모 디렉토리에서 모든 하위 폴더 수집
        all_subfolders = get_subfolders_from_multiple_dirs(parent_dirs)

        if not all_subfolders:
            print("지정된 디렉토리에 하위 폴더가 없습니다.")
            return # 함수 종료

        print("------------------------------------")
        print("사건 폴더 목록:")
        print("------------------------------------")
        for i, (parent_name, dirname, _) in enumerate(all_subfolders):
            print(f"{i + 1: >3}. [{parent_name}] {dirname}") # 부모 디렉토리 정보 포함
        print("------------------------------------")

        while True:
            try:
                choice = input(f"클립보드에 복사할 폴더 번호 (1-{len(all_subfolders)}) 또는 취소(c)를 입력하세요: ")
                if choice.lower() == 'c':
                    print("작업을 취소했습니다.")
                    return # 함수 종료

                choice_num = int(choice)
                if 1 <= choice_num <= len(all_subfolders):
                    parent_name, subdir_name, full_path = all_subfolders[choice_num - 1]
                    print(f"\n선택: [{parent_name}] {subdir_name}")

                    # pyperclip 예외 처리 추가
                    try:
                        pyperclip.copy(full_path)
                        print(f"\n✅ 성공: '{full_path}' 경로가 클립보드에 복사되었습니다.")
                    except pyperclip.PyperclipException as clip_err:
                        print(f"\n❌ 오류: 클립보드 복사 중 문제가 발생했습니다. 에러: {clip_err}")
                        print("수동으로 경로를 복사하세요:")
                        print(full_path)

                    # 파일에 경로 저장
                    try:
                        with open("case_path.txt", "w", encoding="utf-8") as f:
                            f.write(full_path)
                        print(f"✅ 성공: '{full_path}' 경로가 case_path.txt 파일에 저장되었습니다.")
                    except Exception as save_err:
                        print(f"❌ 오류: 경로를 파일에 저장하는 중 문제가 발생했습니다. 에러: {save_err}")
                        print("프로그램이 계속 진행되지만, 다음 단계에서 문제가 발생할 수 있습니다.")

                    break # 성공적으로 복사 후 루프 종료
                else:
                    print(f"❌ 잘못된 번호입니다. 1부터 {len(all_subfolders)} 사이의 번호를 입력하거나 'c'를 입력하세요.")
            except ValueError:
                print("❌ 잘못된 입력입니다. 숫자 또는 'c'를 입력하세요.")
            # 예상치 못한 오류 처리 추가
            except Exception as e:
                print(f"\n❌ 예상치 못한 오류 발생: {e}")
                sys.exit(1) # 심각한 오류 시 종료

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
    # 여러 대상 디렉토리 경로 설정 (Raw string 사용)
    case_folder_paths = [
        r"F:\내 드라이브\LifewithAI@20250120\Legalcases",
        r"F:\내 드라이브\LifewithAI@20250120\Legalcases_(주)리하온",
        r"F:\내 드라이브\LifewithAI@20250120\Legalcases_(주)대구농산"
    ]
    list_and_copy_folder_path(case_folder_paths)

    # 사용자가 결과를 확인하고 종료할 수 있도록 input() 유지
    # 단, 오류 발생 시에는 sys.exit()로 즉시 종료되므로 이 부분은 실행되지 않음
    print("\n------------------------------------")
    input("엔터 키를 누르면 프로그램을 종료합니다...")
