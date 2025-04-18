import os
import shutil
import webbrowser

# 경로 설정
source_folder = r"D:\전자소송다운로드"
backup_base_folder = r"D:\전자소송다운로드 백업"
temp_move_folder_name = "임시이동"
target_folder = os.path.join(backup_base_folder, temp_move_folder_name)

# 웹사이트 URL
url_to_open = "https://ecfs.scourt.go.kr/psp/index.on?m=PSP101M01" # 사용자가 제공한 URL로 수정했습니다.

def move_files_and_open_browser():
    """
    지정된 폴더의 파일을 백업 위치로 이동하고 웹 브라우저를 엽니다.
    """
    try:
        # 1. 소스 폴더 확인 및 파일 이동
        if os.path.exists(source_folder):
            files_in_source = [f for f in os.listdir(source_folder) if os.path.isfile(os.path.join(source_folder, f))]

            if files_in_source:
                print(f"'{source_folder}' 폴더에 파일이 있습니다. 파일을 이동합니다...")

                # 대상 폴더 생성 (없으면)
                os.makedirs(target_folder, exist_ok=True)
                print(f"'{target_folder}' 폴더를 확인/생성했습니다.")

                # 파일 이동
                for filename in files_in_source:
                    source_path = os.path.join(source_folder, filename)
                    destination_path = os.path.join(target_folder, filename)

                    # 대상 폴더에 동일한 이름의 파일이 있으면 덮어쓰지 않고 처리 중단 또는 다른 로직 추가 가능
                    # 여기서는 shutil.move가 기본적으로 덮어쓰므로 그대로 진행
                    shutil.move(source_path, destination_path)
                    print(f"'{filename}' 파일을 '{target_folder}'로 이동했습니다.")

                print(f"'{source_folder}'의 모든 파일을 '{target_folder}'로 이동 완료했습니다.")
            else:
                print(f"'{source_folder}' 폴더가 비어 있습니다. 파일 이동을 건너<0xEB><0x9A><0x8D>니다.")
        else:
            print(f"'{source_folder}' 폴더를 찾을 수 없습니다.")
            # 소스 폴더가 없으면 웹 페이지만 열도록 처리하거나, 오류로 간주할 수 있음
            # 여기서는 웹 페이지만 여는 것으로 진행

        # 2. 웹 브라우저 열기
        print(f"'{url_to_open}' 웹 페이지를 엽니다...")
        # 특정 브라우저(크롬)를 지정하여 열기 시도
        try:
            # Windows에서 기본 브라우저가 아닌 크롬을 지정하는 방법
            # 크롬 실행 파일 경로를 직접 지정해야 할 수 있음
            # 일반적인 경로 예시: 'C:/Program Files/Google/Chrome/Application/chrome.exe %s'
            # webbrowser.get('chrome').open(url_to_open) # 시스템에 'chrome'으로 등록된 경우
            webbrowser.open(url_to_open) # 시스템 기본 브라우저 사용
            print("웹 페이지를 열었습니다.")
        except webbrowser.Error as e:
            print(f"웹 브라우저를 여는 데 실패했습니다: {e}")
            print("시스템 기본 브라우저로 다시 시도합니다.")
            try:
                webbrowser.open(url_to_open)
                print("시스템 기본 브라우저로 웹 페이지를 열었습니다.")
            except webbrowser.Error as e2:
                 print(f"시스템 기본 브라우저로도 열 수 없습니다: {e2}")


    except Exception as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    move_files_and_open_browser()
