# -*- coding: utf-8 -*-
"""
PDF 파일에서 텍스트를 추출하여 마크다운 파일로 저장하는 모듈
"""
import os
import io
import re
import sys
import yaml
import logging
import argparse
import datetime
import concurrent.futures
import platform
from google.cloud import vision
from PIL import Image
import tempfile
from pdf2image import convert_from_path
from dotenv import load_dotenv

# Rich 라이브러리 추가
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
    from rich.logging import RichHandler
    from rich.theme import Theme
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("Rich 라이브러리가 설치되어 있지 않습니다. 기본 출력을 사용합니다.")
    print("Rich 설치 방법: pip install rich")

# 상수 및 설정
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 't')
PARALLEL_PROCESSING = True  # 병렬 처리 사용 여부

# 플랫폼 감지 함수
def detect_platform():
    """현재 플랫폼을 감지하여 플래그를 반환"""
    system = platform.system()
    is_wsl = 'microsoft' in platform.uname().release.lower() or 'WSL' in platform.uname().release
    is_windows = system == "Windows"
    is_mac = system == "Darwin"
    is_linux = system == "Linux"
    
    return {
        'SYSTEM': system,
        'IS_WSL': is_wsl,
        'IS_WINDOWS': is_windows,
        'IS_MAC': is_mac,
        'IS_LINUX': is_linux
    }

# 전역 플랫폼 변수 초기화
_platform_info = detect_platform()
SYSTEM = _platform_info['SYSTEM']
IS_WSL = _platform_info['IS_WSL']
IS_WINDOWS = _platform_info['IS_WINDOWS']
IS_MAC = _platform_info['IS_MAC']
IS_LINUX = _platform_info['IS_LINUX']

# Rich 콘솔 객체 생성
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "phase": "bold blue",
    "filename": "italic yellow",
    "newname": "italic green",
    "page": "bold cyan on dark_cyan",
    "metadata": "italic cyan",
})

console = Console(theme=custom_theme) if RICH_AVAILABLE else None

def get_default_credentials_path():
    """
    플랫폼에 따른 기본 자격 증명 파일 경로를 반환합니다.
    """
    # 함수 내에서 플랫폼 감지 (멀티프로세싱 환경에서 안전)
    platform_info = detect_platform()
    
    if platform_info['IS_WINDOWS']:
        # Windows: C:\Users\username\.config\pdf2text\credentials.json
        home = os.path.expanduser("~")
        return os.path.join(home, ".config", "pdf2text", "credentials.json")
    elif platform_info['IS_WSL']:
        # WSL: /mnt/c/Users/username/.config/pdf2text/credentials.json
        # WSL에서는 Windows 홈 디렉토리를 사용
        import pwd
        username = pwd.getpwuid(os.getuid()).pw_name
        return f"/mnt/c/Users/{username}/.config/pdf2text/credentials.json"
    elif platform_info['IS_MAC'] or platform_info['IS_LINUX']:
        # macOS/Linux: /home/username/.config/pdf2text/credentials.json
        home = os.path.expanduser("~")
        return os.path.join(home, ".config", "pdf2text", "credentials.json")
    else:
        return None

def get_platform_specific_env_var(base_var_name):
    """
    플랫폼별 환경 변수를 찾습니다.
    예: GOOGLE_CLOUD_CREDENTIALS_WSL, GOOGLE_CLOUD_CREDENTIALS_WINDOWS 등
    """
    # 먼저 기본 환경 변수 확인
    value = os.environ.get(base_var_name, '')
    if value:
        return value
    
    # 함수 내에서 플랫폼 감지 (멀티프로세싱 환경에서 안전)
    platform_info = detect_platform()
    
    # 플랫폼별 환경 변수 확인
    if platform_info['IS_WSL']:
        return os.environ.get(f"{base_var_name}_WSL", '')
    elif platform_info['IS_WINDOWS']:
        return os.environ.get(f"{base_var_name}_WINDOWS", '')
    elif platform_info['IS_MAC']:
        return os.environ.get(f"{base_var_name}_MAC", '')
    elif platform_info['IS_LINUX']:
        return os.environ.get(f"{base_var_name}_LINUX", '')
    
    return ''

def get_cross_platform_path(windows_path):
    """
    Windows 경로를 현재 시스템에 맞는 경로로 변환합니다.
    WSL 환경에서는 /mnt/d/ 형식으로, Windows에서는 그대로 사용합니다.
    """
    # 함수 내에서 플랫폼 감지 (멀티프로세싱 환경에서 안전)
    platform_info = detect_platform()
    
    if platform_info['IS_LINUX'] and platform_info['IS_WSL']:
        # WSL 환경에서 Windows 경로를 Linux 경로로 변환
        import re
        
        # 드라이브 문자 패턴 매칭 (예: C:\, D:\\, C:\\\\, C:/)
        # 백슬래시 뿐만 아니라 슬래시도 처리
        match = re.match(r'^([A-Za-z]):[\\/]+(.*)$', windows_path)
        if match:
            drive_letter = match.group(1).lower()
            rest_path = match.group(2)
            # 백슬래시를 슬래시로 변환
            rest_path = rest_path.replace('\\', '/')
            # 연속된 슬래시를 하나로 변경
            rest_path = re.sub(r'/+', '/', rest_path)
            # 끝의 슬래시 제거
            rest_path = rest_path.rstrip('/')
            wsl_path = f"/mnt/{drive_letter}/{rest_path}"
            
            if DEBUG:
                print(f"[DEBUG] Path conversion: '{windows_path}' -> '{wsl_path}'")
            
            return wsl_path
        else:
            # 드라이브 문자가 없는 경우 그대로 반환
            if DEBUG:
                print(f"[DEBUG] No drive letter found in path: '{windows_path}'")
            return windows_path
    else:
        # Windows 또는 기타 환경: 그대로 사용
        return windows_path

# 로깅 설정
def setup_logging(log_level="INFO", log_file=None):
    """로깅 설정"""
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    # 로그 포맷 설정
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 로그 핸들러 설정
    handlers = []
    
    # Rich 로깅 핸들러 사용 (사용 가능한 경우)
    if RICH_AVAILABLE:
        handlers.append(RichHandler(rich_tracebacks=True, console=console))
    else:
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(console_handler)
    
    # 파일 핸들러 (로그 파일이 지정된 경우)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(file_handler)
    
    # 로깅 설정 적용
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )

# 환경 변수 로드
load_dotenv()

# 환경 변수 확인 및 로깅
google_credentials = os.environ.get('GOOGLE_CLOUD_CREDENTIALS', '')
poppler_path = os.environ.get('POPPLER_PATH', '')

# PDF 파일을 이미지로 변환
def pdf_to_images(pdf_path, poppler_path=None):
    """
    PDF 파일을 이미지로 변환
    
    :param pdf_path: PDF 파일 경로
    :param poppler_path: Poppler 경로
    :return: 변환된 이미지 목록
    """
    try:
        # 환경 변수에서 Poppler 경로 가져오기 (설정된 경우)
        if not poppler_path:
            # 플랫폼별 환경 변수 확인
            poppler_path = get_platform_specific_env_var('POPPLER_PATH')
            
            # 환경 변수에 없으면 config에서 가져오기
            if not poppler_path:
                try:
                    # config.yaml 로드
                    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    config_path = os.path.join(script_dir, 'config.yaml')
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    poppler_path = config.get('text_extraction', {}).get('poppler_path', '')
                    if poppler_path:
                        poppler_path = get_cross_platform_path(poppler_path)
                except:
                    pass
            
            # 플랫폼별 처리
            platform_info = detect_platform()
            if platform_info['IS_WSL'] or platform_info['IS_LINUX'] or platform_info['IS_MAC']:
                # Linux/WSL/macOS는 시스템 poppler 사용
                poppler_path = None
                if DEBUG:
                    print(f"[DEBUG] {platform_info['SYSTEM']} detected, using system poppler")
        
        if RICH_AVAILABLE:
            console.print(f"[phase]PDF 파일을 이미지로 변환 중...[/] [filename]{os.path.basename(pdf_path)}[/]")
        else:
            print(f"PDF 파일을 이미지로 변환 중... {os.path.basename(pdf_path)}")
        
        # PDF 파일을 이미지로 변환
        if poppler_path and os.path.exists(poppler_path):
            images = convert_from_path(
                pdf_path, 
                dpi=300, 
                poppler_path=poppler_path,
                fmt="jpeg",
                jpegopt={"quality": 95, "optimize": True, "progressive": True}
            )
        else:
            if RICH_AVAILABLE:
                console.print("[warning]Poppler 경로가 설정되지 않았거나 올바르지 않습니다. 기본 설정으로 시도합니다.[/]")
            # Poppler 경로 없이 시도
            images = convert_from_path(
                pdf_path, 
                dpi=300, 
                fmt="jpeg",
                jpegopt={"quality": 95, "optimize": True, "progressive": True}
            )
        
        if RICH_AVAILABLE:
            console.print(f"[success]PDF 변환 완료:[/] [info]{len(images)}개 페이지[/]")
        else:
            print(f"PDF 변환 완료: {len(images)}개 페이지")
        
        return images
    except Exception as e:
        error_msg = f"PDF 변환 오류: {e}"
        logging.error(error_msg)
        return []

# 이미지에서 텍스트 추출
def detect_text_from_image(image, language_hints=None, credentials_path=None):
    """
    Google Cloud Vision API를 사용하여 이미지 객체에서 텍스트를 추출하는 함수
    
    :param image: PIL Image 객체
    :param language_hints: OCR 언어 힌트 리스트
    :param credentials_path: Google Cloud 인증 파일 경로
    :return: 추출된 텍스트
    """
    if language_hints is None:
        language_hints = ['ko']
    
    # 플랫폼 정보 디버그 출력
    if DEBUG:
        platform_info = detect_platform()
        print(f"[DEBUG] Platform detection in detect_text_from_image:")
        print(f"  - System: {platform_info['SYSTEM']}")
        print(f"  - IS_WINDOWS: {platform_info['IS_WINDOWS']}")
        print(f"  - IS_WSL: {platform_info['IS_WSL']}")
    
    try:
        # 인증 파일 경로 설정
        if not credentials_path:
            # 플랫폼별 환경 변수 확인
            credentials_path = get_platform_specific_env_var('GOOGLE_CLOUD_CREDENTIALS')
            
            # 환경 변수에 없으면 config에서 가져오기
            if not credentials_path:
                try:
                    # config.yaml 로드
                    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    config_path = os.path.join(script_dir, 'config.yaml')
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    original_path = config.get('text_extraction', {}).get('google_credentials_path', '')
                    if original_path:
                        # 항상 경로 변환 시도 (백슬래시가 없어도)
                        credentials_path = get_cross_platform_path(original_path)
                except Exception as e:
                    if DEBUG:
                        print(f"[DEBUG] Error loading config: {e}")
                    pass
            
            # 그래도 없으면 기본 경로 사용
            if not credentials_path:
                default_path = get_default_credentials_path()
                if DEBUG:
                    print(f"[DEBUG] Default credentials path returned: {default_path}")
                if default_path and os.path.exists(default_path):
                    credentials_path = default_path
                    if DEBUG:
                        print(f"[DEBUG] Using default credentials path: {credentials_path}")
                elif default_path:
                    if DEBUG:
                        print(f"[DEBUG] Default path does not exist: {default_path}")
        
        vision_api_available = False
        
        # Google Cloud Vision API 사용
        try:
            # 인증 파일이 존재하는지 확인
            if credentials_path and os.path.exists(credentials_path):
                # 환경 변수 설정
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
                
                # Vision API 클라이언트 초기화
                client = vision.ImageAnnotatorClient()
                vision_api_available = True
            else:
                if RICH_AVAILABLE:
                    if credentials_path:
                        console.print(f"[warning]Google Cloud 인증 파일을 찾을 수 없습니다: {credentials_path}[/]")
                    else:
                        console.print("[warning]Google Cloud 인증 파일 경로가 설정되지 않았습니다.[/]")
                logging.warning(f"Google Cloud 인증 파일을 찾을 수 없습니다: {credentials_path}")
                return ""
            
            if vision_api_available:
                # 이미지를 바이트로 변환
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG')
                content = img_byte_arr.getvalue()
                
                # 이미지 생성
                image = vision.Image(content=content)
                
                # 텍스트 감지 설정
                features = [vision.Feature(type_=vision.Feature.Type.TEXT_DETECTION)]
                
                # 이미지 컨텍스트 설정 (언어 힌트)
                image_context = vision.ImageContext(language_hints=language_hints)
                
                # 텍스트 감지 요청
                response = client.annotate_image({
                    'image': image,
                    'features': features,
                    'image_context': image_context,
                })
                
                # 결과 처리
                if response.error.message:
                    logging.error(f"Google Vision API 오류: {response.error.message}")
                    return ""
                
                # 전체 텍스트 추출
                if response.full_text_annotation:
                    return response.full_text_annotation.text
                
                # 텍스트 주석이 있는 경우
                texts = []
                for text in response.text_annotations:
                    if text.description:
                        texts.append(text.description)
                
                # 첫 번째 텍스트는 전체 텍스트이므로 이를 반환
                if texts:
                    return texts[0]
                
                return ""
            else:
                return ""
        except Exception as vision_error:
            logging.error(f"Google Vision API 오류: {vision_error}")
            return ""
    except Exception as e:
        logging.error(f"이미지에서 텍스트 추출 중 오류 발생: {e}")
        return ""

# 추출된 텍스트 처리
def process_text(text, is_evidence=False):
    """
    추출된 텍스트를 처리하여 가독성을 향상시키는 함수
    
    :param text: 추출된 원본 텍스트
    :param is_evidence: 7번 제출증거 파일 여부
    :return: 처리된 텍스트
    """
    if not text:
        return ""
    
    # 줄 단위로 분리
    lines = text.split('\n')
    processed_lines = []
    
    # 7번 제출증거 파일인 경우 특별 처리
    if is_evidence:
        # 의미 없는 줄, 숫자만 있는 줄, 특수 문자로만 이루어진 줄 건너뛰기
        meaningful_lines = []
        for line in lines:
            line = line.strip()
            
            # 빈 줄 건너뛰기
            if not line:
                continue
            
            # 숫자만 있는 줄 건너뛰기 (페이지 번호 등)
            if re.match(r'^[\d\s\-\.]+$', line):
                continue
            
            # 특수 문자로만 이루어진 줄 건너뛰기
            if re.match(r'^[^\w\s가-힣]+$', line):
                continue
            
            # 페이지 번호 패턴 제거 (예: "- 1 -", "- 2 -")
            if re.match(r'^[\s\-]*\d+[\s\-]*$', line):
                continue
            
            # 짧은 줄이면서 의미 없는 텍스트 건너뛰기
            if len(line) < 5 and not re.search(r'[가-힣]', line):
                continue
            
            # 불필요한 기호 제거
            line = re.sub(r'^\s*[\*\-\•\◦\‣\▪\▫\□\■\◆\◇\○\●\-]+\s*', '', line)
            
            # 줄 끝의 불필요한 문자 제거
            line = re.sub(r'[\-\,\:\;]+$', '', line)
            
            meaningful_lines.append(line)
        
        # 문장 중간의 줄바꿈 연결
        i = 0
        while i < len(meaningful_lines) - 1:
            current_line = meaningful_lines[i]
            next_line = meaningful_lines[i + 1]
            
            # 현재 줄이 문장 중간에서 끝나는지 확인 (마침표, 물음표, 느낌표, 쉼표, 세미콜론 등으로 끝나지 않음)
            if (current_line and not re.search(r'[.?!,;:]\s*$', current_line) and 
                # 다음 줄이 한글로 시작하거나, 숫자로 시작하지 않는 경우
                next_line and (re.match(r'^[가-힣]', next_line) or not re.match(r'^\d+[\.\)\s]', next_line))):
                
                # 줄 연결 시 공백 추가
                meaningful_lines[i] = current_line + ' ' + next_line
                meaningful_lines.pop(i + 1)
            else:
                i += 1
        
        # 중복 공백 제거 및 줄 정리
        for line in meaningful_lines:
            line = re.sub(r'\s+', ' ', line).strip()
            if line:
                processed_lines.append(line)
    else:
        # 8번 제출서면 등 일반 텍스트 처리 (개선된 버전)
        meaningful_lines = []
        for line in lines:
            line = line.strip()
            
            # 빈 줄 건너뛰기
            if not line:
                continue
            
            # 페이지 번호 패턴 제거 (예: "- 1 -", "- 2 -")
            if re.match(r'^[\s\-]*\d+[\s\-]*$', line):
                continue
                
            # 숫자만 있는 줄 건너뛰기 (페이지 번호 등)
            if re.match(r'^[\d\s\-\.]+$', line):
                continue
            
            # 특수 문자로만 이루어진 줄 건너뛰기
            if re.match(r'^[^\w\s가-힣]+$', line):
                continue
                
            # 짧은 줄이면서 의미 없는 텍스트 건너뛰기 (서면에서는 더 짧은 길이도 허용)
            if len(line) < 3 and not re.search(r'[가-힣]', line):
                continue
            
            # 불필요한 기호 제거 (서면에서는 목차 번호 등은 유지)
            if not re.match(r'^\s*\d+[\.\s]', line):  # 숫자로 시작하는 목차는 유지
                line = re.sub(r'^\s*[\*\•\◦\‣\▪\▫\□\■\◆\◇\○\●]+\s*', '', line)
            
            # 줄 끝의 불필요한 문자 제거
            line = re.sub(r'[\-\,\:\;]+$', '', line)
            
            meaningful_lines.append(line)
        
        # 문장 중간의 줄바꿈 연결 (서면에서는 더 적극적으로 연결)
        i = 0
        while i < len(meaningful_lines) - 1:
            current_line = meaningful_lines[i]
            next_line = meaningful_lines[i + 1]
            
            # 목차 번호로 시작하는 줄은 연결하지 않음
            if re.match(r'^\s*\d+[\.\s]', next_line):
                i += 1
                continue
                
            # 현재 줄이 문장 중간에서 끝나는지 확인 (마침표, 물음표, 느낌표로 끝나지 않음)
            if (current_line and not re.search(r'[.?!]\s*$', current_line) and 
                # 다음 줄이 대문자나 숫자+점으로 시작하지 않는 경우 (새로운 문장이나 목차가 아님)
                next_line and not re.match(r'^\d+[\.\)\s]', next_line)):
                
                # 줄 연결 시 공백 추가
                meaningful_lines[i] = current_line + ' ' + next_line
                meaningful_lines.pop(i + 1)
            else:
                i += 1
        
        # 중복 공백 제거 및 줄 정리
        for line in meaningful_lines:
            line = re.sub(r'\s+', ' ', line).strip()
            if line:
                processed_lines.append(line)
    
    # 처리된 텍스트 반환 (8번 제출서면은 빈줄을 하나만 사용)
    if is_evidence:
        return '\n\n'.join(processed_lines)
    else:
        return '\n'.join(processed_lines)

# 이미지에서 텍스트 추출 및 처리
def process_image_to_text(image_data):
    """
    이미지에서 텍스트를 추출하고 처리하는 함수
    
    :param image_data: (이미지, 페이지 번호, 총 페이지 수, 언어 힌트, 인증 파일 경로, 증거 파일 여부) 튜플
    :return: (페이지 번호, 처리된 텍스트) 튜플
    """
    image, page_num, total_pages, language_hints, credentials_path, is_evidence = image_data
    
    try:
        # 이미지에서 텍스트 추출
        text = detect_text_from_image(image, language_hints, credentials_path)
        
        # 텍스트가 없는 경우 빈 페이지로 처리
        if not text:
            if RICH_AVAILABLE:
                console.print(f"[warning]페이지 {page_num}/{total_pages}에서 텍스트를 추출하지 못했습니다.[/]")
            return page_num, f"*페이지 {page_num}에서 텍스트를 추출하지 못했습니다.*"
        
        # 텍스트 처리 (가독성 향상)
        processed_text = process_text(text, is_evidence)
        
        # 7번 제출증거 파일인 경우 추가 처리
        if is_evidence:
            # 페이지 구분 정보 추가
            if RICH_AVAILABLE:
                console.print(f"[info]7번 제출증거 파일 페이지 {page_num}/{total_pages} 처리 완료[/]")
        else:
            # 일반 파일 처리 정보 추가
            if RICH_AVAILABLE:
                console.print(f"[info]페이지 {page_num}/{total_pages} 처리 완료[/]")
        
        return page_num, processed_text
    except Exception as e:
        logging.error(f"이미지 처리 중 오류 발생 (페이지 {page_num}): {e}")
        if RICH_AVAILABLE:
            console.print(f"[error]이미지 처리 중 오류 발생 (페이지 {page_num}): {e}[/]")
        return page_num, f"*페이지 {page_num}에서 텍스트 추출 중 오류가 발생했습니다: {str(e)}*"

# PDF 파일을 마크다운으로 변환
def process_pdf_to_markdown(pdf_path, output_dir, config):
    """
    PDF 파일을 처리하여 텍스트를 추출하고 마크다운 파일로 저장하는 함수
    
    :param pdf_path: PDF 파일 경로
    :param output_dir: 출력 디렉토리
    :param config: 설정 파일 내용
    :return: 출력 파일 경로
    """
    try:
        # 파일명 추출
        filename = os.path.basename(pdf_path)
        filename_without_ext = os.path.splitext(filename)[0]
        
        # 파일명에서 접두어 추출
        prefix = extract_prefix_from_filename(filename)
        
        # 접두어에 해당하는 폴더 경로 생성
        if prefix:
            prefix_folder = os.path.join(output_dir, prefix)
            # 폴더가 없으면 생성
            if not os.path.exists(prefix_folder):
                os.makedirs(prefix_folder)
                if RICH_AVAILABLE:
                    console.print(f"[success]폴더 생성: {prefix_folder}[/]")
                else:
                    logging.info(f"폴더 생성: {prefix_folder}")
            
            # 출력 파일 경로를 접두어 폴더 내로 설정
            output_path = os.path.join(prefix_folder, f"{filename_without_ext}.md")
        else:
            # 접두어가 없는 경우 기본 출력 디렉토리 사용
            output_path = os.path.join(output_dir, f"{filename_without_ext}.md")
        
        if RICH_AVAILABLE:
            console.print(f"\n[info]PDF 변환 및 텍스트 추출 중:[/] \n{output_path}")
        
        # 파일 유형 결정
        file_type = determine_file_type(filename, config)
        
        # 마크다운 템플릿 가져오기
        template = get_markdown_template(file_type, config, filename, pdf_path)
        
        # 텍스트 추출 시도
        all_text = ""
        vision_api_success = False
        
        # Google Cloud Vision API로 시도
        try:
            # 플랫폼별 환경 변수에서 인증 파일 경로 가져오기
            credentials_path = get_platform_specific_env_var('GOOGLE_CLOUD_CREDENTIALS')
            if credentials_path:
                # 환경 변수도 경로 변환 적용
                credentials_path = get_cross_platform_path(credentials_path)
            
            # 환경 변수에 없으면 config에서 가져오기
            if not credentials_path and config:
                original_cred_path = config.get('text_extraction', {}).get('google_credentials_path', '')
                if original_cred_path:
                    credentials_path = get_cross_platform_path(original_cred_path)
            
            # 그래도 없으면 기본 경로 사용
            if not credentials_path:
                default_path = get_default_credentials_path()
                if default_path and os.path.exists(default_path):
                    credentials_path = default_path
            
            # Poppler 경로 설정
            poppler_path = get_platform_specific_env_var('POPPLER_PATH')
            
            # 환경 변수에 없으면 config에서 가져오기
            if not poppler_path and config:
                poppler_path = config.get('text_extraction', {}).get('poppler_path', '')
                if poppler_path:
                    poppler_path = get_cross_platform_path(poppler_path)
            
            # 플랫폼별 처리
            platform_info = detect_platform()
            if platform_info['IS_WSL'] or platform_info['IS_LINUX'] or platform_info['IS_MAC']:
                # Linux/WSL/macOS는 시스템 poppler 사용 (경로 불필요)
                poppler_path = None
            
            # PDF를 이미지로 변환
            if RICH_AVAILABLE:
                console.print(f"PDF 파일을 이미지로 변환 중... {filename}")
            
            images = pdf_to_images(pdf_path, poppler_path)
            
            if RICH_AVAILABLE:
                console.print(f"PDF 변환 완료: {len(images)}개 페이지")
            
            if images:
                # OCR 언어 힌트 설정
                language_hints = ['ko']
                
                # 텍스트 추출 및 마크다운 파일 생성
                if RICH_AVAILABLE:
                    console.print(f"텍스트 추출 및 마크다운 파일 생성 중: \n{output_path}")
                
                # 병렬 처리를 위한 데이터 준비
                is_evidence = file_type == 'evidence'
                image_data = [(img, i+1, len(images), language_hints, credentials_path, is_evidence) for i, img in enumerate(images)]
                
                # 병렬 처리 또는 순차 처리
                # Windows에서는 플랫폼 감지 문제로 인해 항상 순차 처리
                platform_info = detect_platform()
                if PARALLEL_PROCESSING and len(images) > 1 and not platform_info['IS_WINDOWS']:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(images), 4)) as executor:
                        results = list(executor.map(process_image_to_text, image_data))
                else:
                    results = [process_image_to_text(data) for data in image_data]
                
                # 결과 정렬 및 텍스트 결합
                results.sort(key=lambda x: x[0])  # 페이지 번호로 정렬
                
                # 텍스트 결합
                page_texts = [text for _, text in results]
                
                # 빈 페이지 확인
                non_empty_pages = [text for text in page_texts if text.strip()]
                
                if non_empty_pages:
                    # 총 페이지 수 업데이트
                    total_pages = len(page_texts)
                    
                    # 템플릿에 총 페이지 수 추가
                    template = template.replace("{page_count}", str(total_pages))
                    
                    # 파일 유형에 따라 다른 페이지 형식 적용
                    if is_evidence:
                        # 7번 제출증거 파일인 경우 더 압축된 형식으로 표시
                        page_formatted_texts = []
                        for i, text in enumerate(page_texts):
                            if text.strip():
                                page_header = f"---\n\n**<span style=\"color:blue; background-color:#E6F7FF;\">Page {i+1}/{total_pages}</span>**"
                                page_formatted_texts.append(f"{page_header}\n\n{text}")
                        
                        # 페이지 사이의 간격을 줄이고 구분선 추가
                        all_text = "\n\n".join(page_formatted_texts)
                    else:
                        # 8번 제출서면 파일인 경우 기존 형식 유지
                        all_text = "\n\n".join([f"---\n\n***<span style=\"color:blue; background-color:#A6F1E0;\"><big>[Page {i+1}/{total_pages}]</big></span>***\n\n{text}" for i, text in enumerate(page_texts) if text.strip()])
                    
                    vision_api_success = True
                else:
                    logging.warning(f"모든 페이지에서 텍스트를 추출하지 못했습니다: {pdf_path}")
                    if RICH_AVAILABLE:
                        console.print(f"[warning]모든 페이지에서 텍스트를 추출하지 못했습니다.[/]")
            else:
                logging.warning(f"PDF를 이미지로 변환하지 못했습니다: {pdf_path}")
                if RICH_AVAILABLE:
                    console.print(f"[warning]PDF를 이미지로 변환하지 못했습니다.[/]")
        except Exception as e:
            logging.error(f"Vision API로 텍스트 추출 중 오류 발생: {e}")
            if RICH_AVAILABLE:
                console.print(f"[error]Vision API로 텍스트 추출 중 오류 발생: {e}[/]")
        
        # Vision API가 실패한 경우 오류 메시지 표시
        if not vision_api_success:
            if RICH_AVAILABLE:
                console.print(f"[error]텍스트 추출 실패.[/]")
            
            # 텍스트 추출 실패 메시지
            all_text = "## 텍스트 추출 실패\n\n이 PDF 파일에서 텍스트를 추출하지 못했습니다. 파일이 스캔된 이미지일 수 있습니다."
            logging.warning(f"텍스트 추출이 실패했습니다: {pdf_path}")
        
        # 마크다운 파일 생성
        with open(output_path, 'w', encoding='utf-8') as md_file:
            md_file.write(template)
            md_file.write("\n\n")
            md_file.write(all_text)
        
        return output_path
    except Exception as e:
        logging.error(f"PDF 처리 중 오류 발생: {e}")
        if RICH_AVAILABLE:
            console.print(f"[error]PDF 처리 중 오류 발생: {e}[/]")
        return None

# 사건 폴더 내 모든 PDF 파일 처리
def extract_text_from_pdfs(case_folder, config, process_evidence=True):
    """
    사건 폴더 내 모든 PDF 파일 처리
    
    :param case_folder: 사건 폴더 경로
    :param config: 설정 파일 내용
    :param process_evidence: 제출증거(7번) 파일도 처리할지 여부
    :return: 처리된 파일 수, 오류 목록
    """
    # 원본 폴더 경로
    original_folder = os.path.join(case_folder, "원본폴더")
    if not os.path.exists(original_folder):
        error_msg = f"원본 폴더를 찾을 수 없습니다: {original_folder}"
        logging.error(error_msg)
        if RICH_AVAILABLE:
            console.print(f"[error]{error_msg}[/]")
        else:
            print(error_msg)
        return 0, [error_msg]
    
    # 출력 디렉토리를 사건폴더 루트로 설정
    output_dir = case_folder
    if RICH_AVAILABLE:
        console.print(f"[info]마크다운 파일이 접두어에 해당하는 폴더에 저장됩니다: {output_dir}[/]")
    else:
        logging.info(f"마크다운 파일이 접두어에 해당하는 폴더에 저장됩니다: {output_dir}")
    
    # PDF 파일 목록 가져오기
    pdf_files = []
    for file in os.listdir(original_folder):
        file_path = os.path.join(original_folder, file)
        if os.path.isfile(file_path) and file.lower().endswith('.pdf'):
            # 파일명 패턴 확인
            if process_evidence:
                # 모든 PDF 파일 처리
                pdf_files.append(file_path)
            else:
                # 8번 제출서면 파일만 처리
                if file.startswith('8_제출서면'):
                    pdf_files.append(file_path)
    
    if not pdf_files:
        message = "처리할 PDF 파일이 없습니다."
        if RICH_AVAILABLE:
            console.print(f"[warning]{message}[/]")
        else:
            logging.warning(message)
        return 0, []
    
    if RICH_AVAILABLE:
        console.print(f"[info]처리할 PDF 파일 수: {len(pdf_files)}[/]")
    else:
        logging.info(f"처리할 PDF 파일 수: {len(pdf_files)}")
    
    # 병렬 처리 설정
    max_workers = config.get('text_extraction', {}).get('max_workers_files', None)
    if max_workers is None:
        # CPU 코어 수의 절반을 사용 (최소 2개)
        import multiprocessing
        max_workers = max(2, multiprocessing.cpu_count() // 2)
    
    # 처리 결과
    processed_count = 0
    errors = []
    
    # Windows에서는 순차 처리, 그 외 환경에서는 병렬 처리
    platform_info = detect_platform()
    
    if DEBUG:
        print(f"[DEBUG] Platform detection in extract_text_from_pdfs:")
        print(f"  - System: {platform_info['SYSTEM']}")
        print(f"  - IS_WINDOWS: {platform_info['IS_WINDOWS']}")
        print(f"  - IS_WSL: {platform_info['IS_WSL']}")
        print(f"  - Using {'sequential' if platform_info['IS_WINDOWS'] else 'parallel'} processing")
    
    if platform_info['IS_WINDOWS']:
        # Windows에서는 순차 처리 (병렬 처리 시 플랫폼 감지 문제 방지)
        for pdf_path in pdf_files:
            try:
                result = process_pdf_to_markdown(pdf_path, output_dir, config)
                if result:
                    processed_count += 1
                else:
                    errors.append(f"파일 처리 실패: {pdf_path}")
            except Exception as e:
                error_msg = f"파일 처리 중 오류 발생: {pdf_path} - {str(e)}"
                logging.error(error_msg)
                errors.append(error_msg)
    else:
        # Linux/WSL/macOS에서는 병렬 처리
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            # PDF 처리 작업 제출
            future_to_pdf = {executor.submit(process_pdf_to_markdown, pdf_path, output_dir, config): pdf_path for pdf_path in pdf_files}
            
            # 결과 수집
            for future in concurrent.futures.as_completed(future_to_pdf):
                pdf_path = future_to_pdf[future]
                try:
                    result = future.result()
                    if result:
                        processed_count += 1
                    else:
                        errors.append(f"파일 처리 실패: {pdf_path}")
                except Exception as e:
                    error_msg = f"파일 처리 중 오류 발생: {pdf_path} - {str(e)}"
                    logging.error(error_msg)
                    errors.append(error_msg)
    
    return processed_count, errors

# 설정 파일 로드
def load_config(config_path):
    """설정 파일 로드"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logging.error(f"설정 파일 로드 실패: {e}")
        return None

# 사건 폴더 경로 입력 받기
def get_case_folder():
    """사용자에게 사건 폴더 경로 입력 받기"""
    # 먼저 case_path.txt 파일에서 경로 읽기 시도
    case_path_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "case_path.txt")
    
    if os.path.exists(case_path_file):
        try:
            with open(case_path_file, "r", encoding="utf-8") as f:
                saved_path = f.read().strip()
                if saved_path:
                    if RICH_AVAILABLE:
                        console.print(f"\n[info]case_path.txt에 저장된 경로:[/] {saved_path}")
                        use_saved = console.input("[question]이 경로를 사용하시겠습니까? (y/n) [기본값: y]: [/]").lower() or 'y'
                    else:
                        print(f"\ncase_path.txt에 저장된 경로: {saved_path}")
                        use_saved = input("이 경로를 사용하시겠습니까? (y/n) [기본값: y]: ").lower() or 'y'
                    
                    if use_saved == 'y':
                        return saved_path
        except Exception as e:
            logging.warning(f"case_path.txt 파일 읽기 오류: {e}")
    
    # 저장된 경로가 없거나 사용하지 않는 경우 새로 입력 받기
    if RICH_AVAILABLE:
        case_folder = console.input("[question]사건 폴더 경로를 입력하세요: [/]")
    else:
        case_folder = input("사건 폴더 경로를 입력하세요: ")
    
    # 경로에서 따옴표 제거
    case_folder = case_folder.strip('"\'')
    
    return os.path.normpath(case_folder)

def extract_prefix_from_filename(filename):
    """
    파일명에서 접두어 추출 (예: '7_제출증거_', '8_제출서면_', '9_판결_')
    
    :param filename: 파일명
    :return: 접두어 (없으면 None)
    """
    # 접두어 패턴 (숫자_한글문자_)
    prefix_pattern = re.compile(r'^(\d+_[^_]+)_')
    match = prefix_pattern.search(filename)
    
    if match:
        return match.group(1)
    return None

def determine_file_type(filename, config):
    """
    파일명 패턴 매칭을 통한 유형 분류
    
    :param filename: 파일명
    :param config: 설정 파일 내용
    :return: 파일 유형 ('evidence', 'submission', 'judgment' 또는 None)
    """
    # 파일 유형 패턴 가져오기
    evidence_patterns = config.get('text_extraction', {}).get('evidence_template', {}).get('patterns', [])
    submission_patterns = config.get('text_extraction', {}).get('submission_template', {}).get('patterns', [])
    judgment_patterns = config.get('text_extraction', {}).get('judgment_template', {}).get('patterns', [])
    
    # 파일명 패턴 매칭
    for pattern in evidence_patterns:
        if re.search(pattern, filename):
            return 'evidence'
    
    for pattern in submission_patterns:
        if re.search(pattern, filename):
            return 'submission'
    
    for pattern in judgment_patterns:
        if re.search(pattern, filename):
            return 'judgment'
    
    # 파일명 규칙 패턴 확인
    file_naming_rules = config.get('file_naming_rules', {}).get('prefix_patterns', {})
    for prefix, patterns in file_naming_rules.items():
        if prefix.startswith("7_제출증거_") and any(re.search(p, filename) for p in patterns if p):
            return 'evidence'
        elif prefix.startswith("8_제출서면_") and any(re.search(p, filename) for p in patterns if p):
            return 'submission'
        elif prefix.startswith("9_판결_") and any(re.search(p, filename) for p in patterns if p):
            return 'judgment'
    
    # 기본값
    return None

# 마크다운 템플릿 가져오기
def get_markdown_template(file_type, config, filename, pdf_path):
    """
    파일 유형에 맞는 마크다운 템플릿 반환
    
    :param file_type: 파일 유형 (evidence, submission, judgment)
    :param config: 설정 파일 내용
    :param filename: 파일명
    :param pdf_path: PDF 파일 경로
    :return: 마크다운 템플릿
    """
    if file_type == 'evidence':
        template = config.get('text_extraction', {}).get('evidence_template', {}).get('metadata_template', '')
    elif file_type == 'submission':
        template = config.get('text_extraction', {}).get('submission_template', {}).get('metadata_template', '')
    elif file_type == 'judgment':
        template = config.get('text_extraction', {}).get('judgment_template', {}).get('metadata_template', '')
    else:
        template = config.get('default_template', {}).get('metadata_template', '')
    
    # 템플릿 변수 치환
    template_vars = {
        'filename': os.path.splitext(filename)[0],
        'pdf_name_without_ext': os.path.splitext(filename)[0],
        'pdf_path': pdf_path,
        'extraction_date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'datetime': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'page_count': '{page_count}',  # 페이지 수는 나중에 실제 값으로 대체됨
        'total_pages': '{page_count}',  # 총페이지수 변수 추가
        'original_file': pdf_path,  # 원본파일링크 변수 추가
        'original_file_path': pdf_path,  # 원본문서경로 변수 추가
        'original_file_name': filename  # 원본문서이름 변수 추가
    }
    
    # 파일명에서 추가 정보 추출 (예: 날짜, 제출자 등)
    try:
        # 파일명 패턴 분석 (예: 8_제출서면_2023.10.13.자_답변서_피고.pdf)
        parts = os.path.splitext(filename)[0].split('_')
        if len(parts) >= 3:
            if '제출서면' in parts[1]:
                # 제출서면 파일인 경우
                date_part = next((p for p in parts if p.count('.') >= 2), '')
                if date_part:
                    template_vars['date'] = date_part
                
                # 서면 종류 (소장, 답변서 등)
                doc_type = parts[-2] if len(parts) >= 4 else ''
                if doc_type:
                    template_vars['document_type'] = doc_type
                
                # 제출자 (원고, 피고 등)
                submitter = parts[-1] if len(parts) >= 4 else ''
                if submitter:
                    template_vars['submitter'] = submitter
            
            elif '제출증거' in parts[1]:
                # 증거 파일인 경우
                # 날짜 정보 추출
                date_part = next((p for p in parts if p.count('.') >= 2), '')
                if date_part:
                    template_vars['date'] = date_part
                    template_vars['evidence_date'] = date_part
                
                # 증거 종류 (갑 제1호증, 을 제2호증 등)
                evidence_type = parts[-2] if len(parts) >= 4 else ''
                if evidence_type:
                    template_vars['evidence_type'] = evidence_type
                
                # 제출자 (원고, 피고 등)
                submitter = parts[-1] if len(parts) >= 4 else ''
                if submitter:
                    template_vars['submitter'] = submitter
    except Exception as e:
        logging.warning(f"파일명에서 메타데이터 추출 중 오류: {e}")
    
    # 템플릿에 변수 적용
    for key, value in template_vars.items():
        placeholder = f"{{{key}}}"
        if placeholder in template:
            template = template.replace(placeholder, str(value))
    
    return template

# 메인 함수
def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='PDF 파일에서 텍스트를 추출하여 마크다운 파일로 저장하는 스크립트')
    parser.add_argument('--case-folder', help='사건 폴더 경로')
    parser.add_argument('--evidence', action='store_true', help='7번 제출증거 파일도 처리')
    parser.add_argument('--config', default='config.yaml', help='설정 파일 경로')
    parser.add_argument('--debug', action='store_true', help='디버그 모드 활성화')
    parser.add_argument('--max-workers', type=int, help='병렬 처리에 사용할 최대 워커 수')
    parser.add_argument('--max-workers-files', type=int, help='파일 병렬 처리에 사용할 최대 워커 수')
    args = parser.parse_args()
    
    # 디버그 모드 설정
    log_level = "DEBUG" if args.debug else "INFO"
    
    # 설정 파일 로드
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(script_dir, 'config.yaml')
    config = load_config(config_path)
    
    if not config:
        # Rich 사용 가능 여부에 따라 다른 출력
        if RICH_AVAILABLE:
            console.print(f"[error]오류: 설정 파일을 로드할 수 없습니다: {config_path}[/]")
        else:
            print(f"오류: 설정 파일을 로드할 수 없습니다: {config_path}")
        return 1
    
    # 병렬 처리 설정 업데이트
    if args.max_workers and 'text_extraction' in config:
        config['text_extraction']['max_workers'] = args.max_workers
    
    if args.max_workers_files and 'text_extraction' in config:
        config['text_extraction']['max_workers_files'] = args.max_workers_files
    
    # 로깅 설정
    log_file = None
    if 'logging' in config:
        if not log_level == "DEBUG":  # 디버그 모드가 아닌 경우에만 config에서 로그 레벨 가져오기
            log_level = config['logging'].get('level', "INFO")
        log_dir = config['logging'].get('log_dir', "logs")
        log_file_name = config['logging'].get('file', "file_manager.log")
        
        # 로그 디렉토리 생성
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(log_dir, log_file_name)
    
    setup_logging(log_level, log_file)
    
    # 사건 폴더 경로 가져오기
    case_folder = args.case_folder
    if not case_folder:
        if config and config.get('general', {}).get('case_folder'):
            case_folder = config['general']['case_folder']
        else:
            case_folder = get_case_folder()
    
    # 경로에서 따옴표 제거 및 정규화
    case_folder = case_folder.strip('"\'')
    # Windows 경로를 크로스플랫폼 경로로 변환 (필요한 경우)
    if case_folder and '\\' in case_folder:
        case_folder = get_cross_platform_path(case_folder)
    case_folder = os.path.normpath(case_folder)
    
    if RICH_AVAILABLE:
        console.print(f"[phase]처리할 사건 폴더:[/] {case_folder}")
    else:
        print(f"처리할 사건 폴더: {case_folder}")
    logging.info(f"처리할 사건 폴더: {case_folder}")
    
    # 제출증거 파일 처리 여부 확인
    process_evidence = args.evidence
    if not args.evidence:
        if RICH_AVAILABLE:
            console.print("[question]7번 제출증거 파일도 텍스트 추출을 진행하시겠습니까? (y/n) [기본값: y]:[/]", end=" ")
        else:
            print("7번 제출증거 파일도 텍스트 추출을 진행하시겠습니까? (y/n) [기본값: y]:", end=" ")
        
        user_input = input().strip().lower()
        process_evidence = user_input != 'n'
    
    if process_evidence:
        if RICH_AVAILABLE:
            console.print("[info]7번 제출증거 파일도 처리합니다.[/]")
        else:
            print("7번 제출증거 파일도 처리합니다.")
    else:
        if RICH_AVAILABLE:
            console.print("[info]8번 제출서면 파일만 처리합니다.[/]")
        else:
            print("8번 제출서면 파일만 처리합니다.")
    
    # PDF 텍스트 추출 실행
    try:
        if RICH_AVAILABLE:
            console.print("\n[phase]PDF 텍스트 추출을 시작합니다...[/]")
        else:
            print("\nPDF 텍스트 추출을 시작합니다...")
        
        processed_count, errors = extract_text_from_pdfs(case_folder, config, process_evidence)
        
        # 결과 출력
        if RICH_AVAILABLE:
            result_table = Table(title="처리 결과")
            result_table.add_column("항목", style="cyan")
            result_table.add_column("값", style="green")
            
            result_table.add_row("처리된 PDF 파일 수", str(processed_count))
            
            console.print(result_table)
            
            if errors:
                error_table = Table(title="오류 목록")
                error_table.add_column("오류 내용", style="red")
                
                for error in errors:
                    error_table.add_row(error)
                
                console.print(error_table)
        else:
            print("\n처리 완료:")
            print(f"- 처리된 PDF 파일 수: {processed_count}")
            
            if errors:
                print("\n오류 목록:")
                for error in errors:
                    print(f"- {error}")
    except Exception as e:
        logging.exception("PDF 텍스트 추출 중 오류가 발생했습니다.")
        if RICH_AVAILABLE:
            console.print(f"[error]오류가 발생했습니다:[/] {str(e)}")
            import traceback
            console.print_exception()
        else:
            print(f"\n오류가 발생했습니다: {str(e)}")
            import traceback
            print(traceback.format_exc())
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())