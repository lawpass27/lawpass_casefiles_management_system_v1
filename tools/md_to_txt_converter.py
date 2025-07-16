import os
from pathlib import Path

def convert_md_to_txt(folder_path_str):
    """
    지정된 폴더 내의 마크다운 파일을 텍스트 파일로 변환합니다.
    하위 폴더는 제외하며, 기존 텍스트 파일이 있어도 덮어<0xEC<0x93>니다.

    Args:
        folder_path_str (str): 작업할 폴더 경로 문자열.
    """
    try:
        # 입력 경로 문자열에서 양 끝의 큰따옴표 제거
        cleaned_path_str = folder_path_str.strip('"')
        folder_path = Path(cleaned_path_str)

        if not folder_path.is_dir():
            print(f"오류: '{cleaned_path_str}'는 유효한 폴더 경로가 아닙니다.")
            return

        print(f"'{folder_path}' 폴더에서 마크다운 파일을 검색하여 텍스트로 변환합니다 (덮어쓰기 모드)...")

        converted_count = 0
        error_count = 0

        for item in folder_path.iterdir():
            # 파일이고 확장자가 .md 인 경우에만 처리
            if item.is_file() and item.suffix.lower() == '.md':
                md_file_path = item
                txt_file_path = md_file_path.with_suffix('.txt')

                # # 동일한 이름의 .txt 파일이 이미 존재하는지 확인 -> 제거됨
                # if txt_file_path.exists():
                #     print(f"건너<0xEB><0x9A><0x81>: '{txt_file_path.name}' 파일이 이미 존재합니다.")
                #     skipped_count += 1
                #     continue

                try:
                    # 마크다운 파일 읽기 (UTF-8 시도, 실패 시 다른 인코딩 시도)
                    try:
                        md_content = md_file_path.read_text(encoding='utf-8')
                    except UnicodeDecodeError:
                        try:
                            # Windows 환경에서 자주 사용되는 cp949 시도
                            md_content = md_file_path.read_text(encoding='cp949')
                            print(f"정보: '{md_file_path.name}' 파일은 cp949 인코딩으로 읽었습니다.")
                        except Exception as decode_err:
                            print(f"오류: '{md_file_path.name}' 파일 인코딩 감지 실패 - {decode_err}")
                            error_count += 1
                            continue # 다음 파일로 넘어감

                    # 텍스트 파일 쓰기 (UTF-8, 덮어쓰기)
                    txt_file_path.write_text(md_content, encoding='utf-8')
                    print(f"변환 완료 (덮어쓰기): '{md_file_path.name}' -> '{txt_file_path.name}'")
                    converted_count += 1
                except Exception as e:
                    print(f"오류: '{md_file_path.name}' 파일 처리 중 오류 발생 - {e}")
                    error_count += 1

        print(f"\n작업 완료. 변환된 파일: {converted_count}개, 오류 발생: {error_count}개")

    except Exception as e:
        print(f"스크립트 실행 중 오류 발생: {e}")

if __name__ == "__main__":
    target_folder_raw = input("마크다운 파일을 텍스트로 변환할 폴더 경로를 입력하세요: ")
    # 입력된 경로 문자열의 양 끝에서 큰따옴표 제거
    target_folder = target_folder_raw.strip('"')
    convert_md_to_txt(target_folder)