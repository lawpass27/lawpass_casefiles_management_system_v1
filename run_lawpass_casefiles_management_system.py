import os
import sys
import subprocess
import time
from typing import Tuple

def get_user_confirmation(step_number: int, script_name: str, case_folder: str) -> Tuple[bool, bool]:
    """
    각 단계 실행 전 사용자 확인을 받는 함수

    Args:
        step_number: 단계 번호
        script_name: 실행할 스크립트 이름
        case_folder: 사건 폴더 경로

    Returns:
        Tuple[bool, bool]: (계속 진행 여부, 건너뛰기 여부)
    """
    print(f"\n{'='*50}")
    print(f"Step {step_number} 실행 준비: {script_name}")
    if case_folder:
        print(f"사건 폴더: {case_folder}")
    print('='*50)

    # 단계별 추가 정보 표시
    if step_number == 1:
        print("이 단계에서는 사건 폴더를 선택합니다.")
    elif step_number == 2:
        print("이 단계에서는 선택한 사건 폴더에 표준 폴더 구조를 생성합니다.")
        print("생성될 폴더: 0_INBOX, 1_기본정보, 2_사건개요, 3_기준판례, 등")
    elif step_number == 3:
        print("이 단계에서는 전자소송 다운로드 폴더에서 사건 폴더로 파일을 복사합니다.")
        print(f"원본 폴더: {os.path.join(case_folder, '원본폴더')}")
    elif step_number == 4:
        print("이 단계에서는 복사된 파일의 이름을 표준 규칙에 맞게 변경합니다.")
    elif step_number == 5:
        print("이 단계에서는 PDF 파일에서 텍스트를 추출하여 마크다운 파일로 저장합니다.")

    while True:
        choice = input("\n이 단계를 실행하시겠습니까? (y: 실행, n: 종료, s: 건너뛰기, 엔터: 실행): ").lower()
        if choice == 'y' or choice == '':
            return True, False  # (계속 진행, 건너뛰기 안함)
        elif choice == 'n':
            print("사용자 요청으로 프로그램을 종료합니다.")
            return False, False  # (종료, 건너뛰기 안함)
        elif choice == 's':
            print(f"Step {step_number}을(를) 건너뜁니다.")
            return True, True  # (계속 진행, 건너뛰기)
        else:
            print("잘못된 입력입니다. 'y', 'n', 's' 또는 엔터를 입력하세요.")

def confirm_and_modify_path(path, description):
    """
    경로를 확인하고 필요한 경우 수정할 수 있는 함수

    Args:
        path: 확인할 경로
        description: 경로에 대한 설명

    Returns:
        str: 확인되거나 수정된 경로
    """
    print(f"\n현재 {description}: {path}")

    while True:
        choice = input("이 경로를 사용하시겠습니까? (y: 사용, n: 수정, 엔터: 사용): ").lower()
        if choice == 'y' or choice == '':
            return path
        elif choice == 'n':
            new_path = input("새 경로를 입력하세요: ").strip()
            if os.path.exists(new_path):
                print(f"✅ 새 경로가 확인되었습니다: {new_path}")

                # 새 경로를 case_path.txt에 저장
                try:
                    with open("case_path.txt", "w", encoding="utf-8") as f:
                        f.write(new_path)
                    print("✅ 새 경로가 case_path.txt 파일에 저장되었습니다.")
                except Exception as e:
                    print(f"❌ 경로 저장 중 오류 발생: {e}")

                return new_path
            else:
                print(f"❌ 지정된 경로가 존재하지 않습니다: {new_path}")
        else:
            print("잘못된 입력입니다. 'y', 'n' 또는 엔터를 입력하세요.")

def verify_step_result(step_number: int, case_folder: str) -> Tuple[bool, str]:
    """각 스텝의 결과물을 검증하는 함수"""
    try:
        if step_number == 2:
            # Step 2: 표준 폴더 구조 확인
            required_folders = [
                "0_INBOX", "1_기본정보", "2_사건개요", "3_기준판례",
                "4_사실관계", "5_관련법리", "6_논리구성", "7_제출증거",
                "8_제출서면", "9_판결"
            ]
            for folder in required_folders:
                if not os.path.exists(os.path.join(case_folder, folder)):
                    return False, f"필수 폴더가 없습니다: {folder}"
            return True, "표준 폴더 구조 확인 완료"

        elif step_number == 3:
            # Step 3: 원본 폴더와 파일 복사 확인
            original_folder = os.path.join(case_folder, "원본폴더")
            if not os.path.exists(original_folder):
                return False, "원본폴더가 생성되지 않았습니다"

            # 최소 1개 이상의 파일 존재 확인
            if not any(os.listdir(original_folder)):
                return False, "원본폴더에 복사된 파일이 없습니다"
            return True, "파일 복사 확인 완료"

        elif step_number == 4:
            # Step 4: 파일 이름 변경 확인
            # 적어도 하나의 파일이 표준 이름 형식을 따르는지 확인
            original_folder = os.path.join(case_folder, "원본폴더")
            has_renamed = False
            for filename in os.listdir(original_folder):
                if any(filename.startswith(prefix) for prefix in
                      ["1_기본정보_", "7_제출증거_", "8_제출서면_", "9_판결_"]):
                    has_renamed = True
                    break
            if not has_renamed:
                return False, "이름이 변경된 파일을 찾을 수 없습니다"
            return True, "파일 이름 변경 확인 완료"

        elif step_number == 5:
            # Step 5: 텍스트 추출 결과 확인
            # 최소 1개 이상의 마크다운 파일 존재 확인
            md_files_exist = False
            for _, _, files in os.walk(case_folder):
                if any(f.endswith('.md') for f in files):
                    md_files_exist = True
                    break
            if not md_files_exist:
                return False, "생성된 마크다운 파일을 찾을 수 없습니다"
            return True, "텍스트 추출 결과 확인 완료"

        return True, "검증 단계 없음"
    except Exception as e:
        return False, f"결과 검증 중 오류 발생: {e}"

def run_step(step_number: int, script_name: str, case_folder: str) -> bool:
    """각 스텝을 실행하고 결과를 검증하는 함수"""
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script_name)

    print(f"\n{'='*50}")
    print(f"Step {step_number} 실행: {script_name}")
    print(f"사건 폴더: {case_folder}")
    print('='*50)

    try:
        # 스텝 실행 - Step 1은 대화형으로 실행
        if step_number == 1:
            # 대화형 모드로 실행 (capture_output=False)
            result = subprocess.run([sys.executable, script_path],
                                 capture_output=False, text=True)
        elif step_number == 5:
            # Step 5는 --case-folder 형태로 인수 전달, 대화형 모드로 실행
            print("\nStep 5 실행 중... 진행 상황이 터미널에 표시됩니다.")
            result = subprocess.run([sys.executable, script_path, "--case-folder", case_folder, "--evidence"],
                                 capture_output=False, text=True)
        else:
            result = subprocess.run([sys.executable, script_path, case_folder],
                                 capture_output=True, text=True)
            # 출력 표시
            if result.stdout:
                print("\n출력:")
                print(result.stdout)
            if result.stderr:
                print("\n오류:")
                print(result.stderr)

        # 실행 결과 확인
        if result.returncode != 0:
            print(f"\n❌ Step {step_number} 실행 실패 (종료 코드: {result.returncode})")
            return False

        # 결과물 검증
        if step_number > 1:  # Step 1은 검증 제외
            success, message = verify_step_result(step_number, case_folder)
            if not success:
                print(f"\n❌ Step {step_number} 결과물 검증 실패: {message}")
                return False
            print(f"\n✓ {message}")

        print(f"\n✅ Step {step_number} 실행 완료")
        return True

    except Exception as e:
        print(f"\n❌ Step {step_number} 실행 중 오류 발생: {e}")
        return False

def main():
    """메인 실행 함수"""
    print("법률사건 문서 처리 파이프라인 시작\n")

    # Step 1 실행 전 사용자 확인
    continue_execution, skip_step = get_user_confirmation(1, "step1_copy_case_path.py", "")
    if not continue_execution:
        return 1

    if not skip_step:
        # Step 1 실행 및 사건 폴더 경로 획득
        print("Step 1: 사건 폴더 선택")
        print("사건 폴더를 선택하고 엔터를 누르면 다음 단계로 진행합니다...")
        print("사건 폴더 목록이 표시되지 않으면 경로를 확인해주세요.")

        # step1_copy_case_path.py 실행
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "step1_copy_case_path.py")
        print(f"Step 1 스크립트 경로: {script_path}")
        success = run_step(1, "step1_copy_case_path.py", "")  # case_folder는 step1에서 결정
        if not success:
            print("❌ Step 1 실패. 프로그램을 종료합니다.")
            return 1

        # 사용자가 엔터를 누르기를 기다림
        input("\n사건 폴더 선택이 완료되었습니다. 엔터를 누르면 다음 단계로 진행합니다...")

    # step1_copy_case_path.py 실행 후 생성된 case_path.txt 파일에서 경로를 읽어옴
    try:
        with open("case_path.txt", "r", encoding="utf-8") as f:
            case_folder = f.readline().strip()

        # 경로 확인 및 수정
        case_folder = confirm_and_modify_path(case_folder, "사건 폴더 경로")

        if not os.path.exists(case_folder):
            print(f"❌ 지정된 폴더가 존재하지 않습니다: {case_folder}")
            return 1
        print(f"\n선택된 사건 폴더: {case_folder}")
    except FileNotFoundError:
        print("❌ case_path.txt 파일을 찾을 수 없습니다. Step 1이 정상적으로 실행되었는지 확인하세요.")
        return 1
    except Exception as e:
        print(f"❌ case_path.txt 파일을 읽는 중 오류 발생: {e}")
        return 1

    # 각 스텝 실행
    steps = [
        (2, "step2_create_standard_folders.py"),
        (3, "step3_casefiles_importer.py"),
        (4, "step4_casefiles_renamer.py"),
        (5, "step5_casefiles_extractor.py")
    ]

    for step_number, script_name in steps:  # Step 1은 이미 실행했으므로 제외
        # 각 스텝 실행 전 사용자 확인
        continue_execution, skip_step = get_user_confirmation(step_number, script_name, case_folder)
        if not continue_execution:
            return 1

        if skip_step:
            print(f"Step {step_number} 건너뛰기")
            continue

        # 각 스텝 사이에 잠시 대기
        time.sleep(1)

        # 스텝 실행
        success = run_step(step_number, script_name, case_folder)
        if not success:
            print(f"\n❌ Step {step_number} 실패로 인해 파이프라인을 종료합니다.")
            return 1

    print("\n✅ 모든 스텝이 성공적으로 완료되었습니다!")
    return 0

if __name__ == "__main__":
    sys.exit(main())