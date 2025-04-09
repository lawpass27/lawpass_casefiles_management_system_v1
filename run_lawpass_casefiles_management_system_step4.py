import os
import sys
import time
import subprocess
from typing import Tuple

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
    print("법률사건 문서 처리 파이프라인 시작 (Step 4까지 실행)\n")

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

    # 각 스텝 실행 (Step 4까지만)
    steps = [
        (2, "step2_create_standard_folders.py"),
        (3, "step3_casefiles_importer.py"),
        (4, "step4_casefiles_renamer.py")
    ]

    for step_number, script_name in steps:
        # 각 스텝 사이에 잠시 대기
        time.sleep(1)

        # 스텝 실행
        success = run_step(step_number, script_name, case_folder)
        if not success:
            print(f"\n❌ Step {step_number} 실패로 인해 파이프라인을 종료합니다.")
            return 1

    print("\n✅ Step 4까지 모든 스텝이 성공적으로 완료되었습니다!")
    return 0

if __name__ == "__main__":
    sys.exit(main())