#!/usr/bin/env python3
# folder_packager.py
# 폴더를 repomix로 처리하여 동일한 위치에 _repomix.txt 파일로 저장하는 범용 폴더 패키징 도구

import os
import sys
import subprocess
from datetime import datetime

def package_folder(folder_path):
    """
    폴더를 repomix로 처리하여 동일한 위치에 _repomix.txt 파일로 저장합니다.
    
    Args:
        folder_path (str): 처리할 폴더의 전체 경로
        
    Returns:
        bool: 처리 성공 여부
    """
    try:
        # 경로 정규화 및 존재 여부 확인
        folder_path = os.path.normpath(folder_path)
        if not os.path.exists(folder_path):
            print(f"오류: 경로를 찾을 수 없습니다: {folder_path}")
            return False
            
        if not os.path.isdir(folder_path):
            print(f"오류: 폴더 경로가 아닙니다: {folder_path}")
            return False
            
        # 폴더 이름 추출 및 출력 파일 경로 설정
        folder_name = os.path.basename(folder_path)
        # 출력 파일은 입력한 폴더 안에 생성
        output_file = os.path.join(folder_path, f"{folder_name}_repomix.txt")
        
        # 기존 파일이 있으면 덮어쓰기 (백업 없음)
        if os.path.exists(output_file):
            print(f"기존 파일을 덮어씁니다: {output_file}")
        
        # repomix 실행
        print(f"폴더 처리 중: {folder_path}")
        command = [
            "npm.cmd",
            "exec",
            "--yes",  # 자동으로 yes 응답
            "repomix",
            "--",
            "-o", output_file,
            "--style", "plain",
            folder_path
        ]

        # 명령어 실행 (인코딩 문제 방지를 위해 errors='replace' 추가)
        result = subprocess.run(command, capture_output=True, text=True, errors='replace')
        
        if result.returncode == 0:
            print(f"\n처리 완료: {output_file}")
            return True
        else:
            print(f"오류 발생: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"예상치 못한 오류가 발생했습니다: {str(e)}")
        return False

def main():
    """메인 함수"""
    print("=" * 50)
    print("폴더 패키징 도구 - repomix 기반")
    print("=" * 50)
    
    # 명령줄 인수가 있는지 확인
    if len(sys.argv) > 1:
        target_path = sys.argv[1]
    else:
        # 사용자로부터 경로 입력 받기
        target_path = input("\n패키징할 폴더의 경로를 입력하세요: ")
    
    # 경로 전처리 (따옴표 제거)
    target_path = target_path.strip('"\'')
    
    # 처리 실행
    success = package_folder(target_path)
    
    if success:
        print("\n패키징이 성공적으로 완료되었습니다.")
    else:
        print("\n패키징 중 오류가 발생했습니다.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n프로그램이 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n프로그램 실행 중 오류 발생: {str(e)}")
        sys.exit(1)
