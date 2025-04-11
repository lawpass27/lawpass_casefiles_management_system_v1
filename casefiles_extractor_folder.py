# -*- coding: utf-8 -*-
"""
general_text_extractor.py

지정된 폴더 내의 모든 PDF 및 이미지 파일에서 텍스트를 추출하여,
각 원본 파일과 동일한 이름의 마크다운 파일을 동일한 폴더에 생성합니다.
추출 및 마크다운 형식은 기존 3_casefiles_extractor.py의 로직을 참조하도록 수정되었습니다.
(페이지 구분 유지, 페이지 수 정보 전달, 템플릿 교체 준비)
"""

import os
import sys
import re
import argparse
import yaml
import logging
import io
import time
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
import traceback

# --- 필수 라이브러리 임포트 ---
try:
    from pdf2image import convert_from_path
    from PIL import Image, UnidentifiedImageError # UnidentifiedImageError 추가
    from google.cloud import vision
    from dotenv import load_dotenv
except ImportError as e:
    print(f"오류: 필수 라이브러리가 설치되지 않았습니다: {e}")
    print("터미널에서 다음 명령어를 실행하여 설치하세요:")
    print("pip install pdf2image Pillow google-cloud-vision python-dotenv PyYAML rich")
    sys.exit(1)

# --- 환경 변수 로드 ---
# 스크립트 위치와 현재 작업 디렉토리 양쪽에서 .env 파일 로드 시도
try:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'))
    load_dotenv(dotenv_path=os.path.join(SCRIPT_DIR, '.env'))
    print("정보: .env 파일 로드 시도 완료.")
except Exception as e:
    print(f"경고: .env 파일 로드 중 오류 발생 - {e}")

# --- Rich 라이브러리 설정 (선택적) ---
try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn, TimeElapsedColumn
    from rich.logging import RichHandler
    from rich.theme import Theme
    RICH_AVAILABLE = True
    custom_theme = Theme({
        "info": "cyan",
        "success": "bold green",
        "warning": "yellow",
        "error": "bold red",
        "question": "bold yellow",
        "filename_original": "dim yellow",
        "filename_new": "yellow",
        "skipped": "dim cyan",
        "debug": "dim blue",
        "path": "italic blue",
        "phase": "bold magenta" # 추가 (단계 표시용)
    })
    console = Console(theme=custom_theme)
except ImportError:
    RICH_AVAILABLE = False
    console = None
    print("정보: Rich 라이브러리가 없어 기본 터미널 출력을 사용합니다. (pip install rich)")

# --- 로깅 설정 ---
# Logger 인스턴스 생성
logger = logging.getLogger("GeneralExtractor")

def setup_logging(level="INFO", log_file=None):
    """로깅 기본 설정 적용"""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # 기존 핸들러 제거 (중복 방지)
    if logger.hasHandlers():
        logger.handlers.clear()

    logger.setLevel(numeric_level)

    handlers = []
    # Rich Handler 또는 Stream Handler
    if RICH_AVAILABLE:
        rich_handler = RichHandler(rich_tracebacks=True, markup=True, console=console, level=numeric_level, show_path=False)
        rich_handler.setFormatter(logging.Formatter(log_format, date_format))
        handlers.append(rich_handler)
    else:
        stream_handler = logging.StreamHandler()
        stream_handler.setLevel(numeric_level)
        formatter = logging.Formatter(log_format, date_format)
        stream_handler.setFormatter(formatter)
        handlers.append(stream_handler)

    # File Handler (경로가 제공된 경우)
    if log_file:
        try:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
            from logging.handlers import RotatingFileHandler
            # 5MB 크기, 3개 백업
            file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
            file_handler.setLevel(numeric_level)
            formatter = logging.Formatter(log_format, date_format)
            file_handler.setFormatter(formatter)
            handlers.append(file_handler)
            print(f"정보: 로그 파일 저장 위치: {log_file}")
        except Exception as e:
            print(f"오류: 로그 파일 핸들러 설정 실패 - {e}")

    # 핸들러 추가
    for handler in handlers:
        logger.addHandler(handler)

# --- 메시지 출력 함수 ---
def print_message(message, level="info", **kwargs):
    """콘솔 출력 및 로깅 동시 수행"""
    log_level_map = {"debug": logging.DEBUG, "info": logging.INFO, "warning": logging.WARNING, "error": logging.ERROR, "critical": logging.CRITICAL, "success": logging.INFO, "question": logging.INFO, "path": logging.INFO, "phase": logging.INFO} # phase 추가
    log_level = log_level_map.get(level.lower(), logging.INFO)
    # 로그에는 Rich 태그 제거
    log_message = re.sub(r'\[/?.*?\]', '', message)
    logger.log(log_level, log_message)

    # 콘솔 출력 (Rich 사용 가능 시)
    if RICH_AVAILABLE:
        style = level if level in custom_theme.styles else "info"
        console.print(f"[{style}]{message}[/]", **kwargs)
    else:
        prefix = f"[{level.upper()}] " if level not in ["info", "success", "phase"] else ""
        print(f"{prefix}{message}", **kwargs)

# --- 설정 관리 ---
def load_config(config_path):
    """YAML 설정 파일 로드"""
    if not config_path or not os.path.exists(config_path):
        logger.warning(f"설정 파일을 찾을 수 없음: {config_path}")
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
            logger.info(f"설정 파일 로드 완료: {config_path}")
            return config_data
    except FileNotFoundError:
        logger.warning(f"설정 파일을 찾을 수 없음: {config_path}")
        return None
    except yaml.YAMLError as e:
        logger.error(f"설정 파일 파싱 오류: {config_path} - {e}")
        return None
    except Exception as e:
        logger.error(f"설정 파일 로드 중 알 수 없는 오류: {config_path} - {e}")
        return None

def create_default_config():
    """기본 설정값 생성"""
    # 환경 변수에서 기본값 가져오기 시도
    google_creds_from_env = os.environ.get('GOOGLE_CLOUD_CREDENTIALS', '')
    poppler_from_env = os.environ.get('POPPLER_PATH', '')

    return {
        'text_extraction': {
            'enabled': True,
            'use_ocr': True,
            'ocr_language_hints': ['ko', 'en'], # 한국어/영어 동시 지원
            'ocr_dpi': 300, # DPI 기본값
            'google_credentials_path': google_creds_from_env
        },
        'external_tools': {
             'poppler_path': poppler_from_env
        },
        'logging': {
             'level': 'INFO',
             'log_dir': 'logs',
             'file': 'general_extractor.log'
        },
        'folder_names': {}, # 이 스크립트에서는 사용하지 않음
        'file_naming_rules': {'prefix_patterns': {}} # 파일 유형 감지에 필요할 수 있음
    }

def merge_configs(base_config, user_config):
    """설정 병합 (User config 우선)"""
    if not user_config: return base_config
    merged = base_config.copy()
    for key, value in user_config.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key] = merge_configs(merged[key], value)
        else:
            merged[key] = value
    logger.debug("기본 설정과 사용자 설정 병합 완료.")
    return merged

# --- 핵심 로직 (single_casefile_extractor 3.py 기반) ---
# PDF -> 이미지 변환
def convert_pdf_to_images(pdf_path, dpi=300, poppler_path_from_config=None):
    """PDF 파일을 이미지 리스트로 변환"""
    poppler_path_to_use = poppler_path_from_config or os.environ.get('POPPLER_PATH')
    logger.info(f"PDF 이미지 변환 시작: '{os.path.basename(pdf_path)}', DPI: {dpi}, Poppler: '{poppler_path_to_use or '시스템 PATH'}'")

    if not poppler_path_to_use and sys.platform == 'win32':
        print_message("경고: Poppler 경로가 설정되지 않았습니다. 시스템 PATH에 poppler/bin이 포함되어 있는지 확인하세요.", "warning")

    try:
        images = convert_from_path(
            pdf_path,
            dpi=dpi,
            poppler_path=poppler_path_to_use if poppler_path_to_use else None,
            fmt='jpeg', # JPEG 형식 사용 (용량 및 호환성)
            thread_count=max(1, os.cpu_count() // 2) # 사용 가능 CPU의 절반 사용
        )
        if not images:
            print_message(f"정보: '{os.path.basename(pdf_path)}'에서 이미지를 생성하지 못했습니다 (빈 PDF?).", "warning")
        else:
            logger.info(f"PDF에서 {len(images)}개 페이지 이미지 변환 완료.")
        return images
    except Exception as e:
        logger.error(f"PDF 이미지 변환 오류: {pdf_path} - {e}", exc_info=True)
        error_str = str(e).lower()
        if "poppler" in error_str or "pdfinfo" in error_str or "pdftoppm" in error_str:
            print_message("오류: PDF 이미지 변환 실패. Poppler 설치 및 경로 설정을 확인하세요.", "error")
            print_message(f"  (시도된 Poppler 경로: {poppler_path_to_use or '시스템 PATH'})", "error")
        else:
            print_message(f"오류: PDF 변환 중 예상치 못한 문제 발생 - {e}", "error")
        return []

# 이미지 텍스트 추출 (병렬처리용)
def detect_text_from_image(image_data):
    """단일 이미지에서 텍스트 추출 (Google Vision API 사용)"""
    page_index, image, language_hints, credentials_path = image_data
    logger.debug(f"페이지 {page_index + 1} 텍스트 추출 시작...")

    try:
        if not credentials_path or not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Google Cloud 인증 파일을 찾을 수 없습니다: {credentials_path}")

        # 각 스레드/프로세스에서 환경 변수 설정이 필요할 수 있음
        # os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        # => Client 생성 시 credentials_path 직접 사용하는 것이 더 안정적일 수 있음
        client_options = {}
        if credentials_path:
             client_options['credentials_path'] = credentials_path
        
        # client = vision.ImageAnnotatorClient(**client_options) # options 사용 불가 -> 직접 설정 필요
        # 스레드 안전성을 위해 각 작업마다 client를 생성하거나, client 객체 자체를 인수로 전달해야 함.
        # 여기서는 환경 변수를 사용한 기존 방식 유지 (호출 전에 설정되었다고 가정)
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
        client = vision.ImageAnnotatorClient()


        img_byte_arr = io.BytesIO()
        image.save(img_byte_arr, format='JPEG', quality=90) # JPEG 품질 조정
        content = img_byte_arr.getvalue()

        vis_image = vision.Image(content=content)
        # 문서 텍스트 감지 기능 사용
        features = [vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)]
        image_context = vision.ImageContext(language_hints=language_hints)

        response = client.annotate_image({
            'image': vis_image,
            'features': features,
            'image_context': image_context,
        })

        if response.error.message:
            raise Exception(f"Google Vision API Error (페이지 {page_index + 1}): {response.error.message}")

        extracted_text = response.full_text_annotation.text if response.full_text_annotation else ""
        if not extracted_text and response.text_annotations:
            extracted_text = response.text_annotations[0].description # Fallback
            logger.debug(f"페이지 {page_index + 1}: Text annotations[0] 사용됨.")
        elif not extracted_text:
            logger.warning(f"페이지 {page_index + 1}: API 응답에서 텍스트를 찾을 수 없음.")

        log_preview = (extracted_text[:80] + '...') if len(extracted_text) > 80 else extracted_text
        logger.debug(f"페이지 {page_index + 1} OCR 결과 (미리보기): {log_preview.replace(chr(10), ' ')}")
        return page_index, extracted_text

    except FileNotFoundError as fnf_error:
        logger.error(f"페이지 {page_index + 1} 처리 중 인증 파일 오류: {fnf_error}")
        return page_index, f"*** Google Cloud 인증 오류 ***"
    except Exception as e:
        logger.error(f"페이지 {page_index + 1} 텍스트 추출 중 오류: {e}", exc_info=True)
        return page_index, f"*** 페이지 {page_index + 1} 텍스트 추출 오류: {e} ***"

# 텍스트 정제 (step5_casefiles_extractor.py의 process_text 로직 통합)
def clean_text(text, is_evidence=False):
    """
    추출된 텍스트를 처리하여 가독성을 향상시키는 함수 (파일 유형별 처리 적용)

    :param text: 추출된 원본 텍스트 (페이지 구분자 포함 가능)
    :param is_evidence: 7번 제출증거 파일 여부
    :return: 처리된 텍스트 (페이지 구분자 유지)
    """
    if not text: return ""
    logger.debug(f"clean_text: 텍스트 정리 시작 (is_evidence={is_evidence})...")

    original_separator = "\n\n--- Page Break ---\n\n"
    placeholder = "[---PAGE_BREAK_PLACEHOLDER---]"
    text_with_placeholder = text.replace(original_separator, placeholder)
    pages = text_with_placeholder.split(placeholder)
    cleaned_pages = []
    logger.debug(f"clean_text: {len(pages)} 페이지 분리됨.")

    for i, page_content in enumerate(pages):
        # 오류 메시지 포함 페이지는 원본 유지
        if f"*** 페이지 {i + 1}" in page_content or "*** Google Cloud 인증 오류 ***" in page_content:
            logger.warning(f"clean_text: 페이지 {i+1}에 오류 문자열 포함, 원본 유지: {page_content[:100]}")
            cleaned_pages.append(page_content)
            continue

        lines = page_content.split('\n')
        processed_lines = []
        meaningful_lines = []

        # 1단계: 의미 있는 라인 필터링
        for line in lines:
            line = line.strip()
            if not line: continue

            # 페이지 번호 패턴 제거
            if re.match(r'^[\s\-]*\d+[\s\-]*$', line) and len(line) < 7:
                logger.debug(f"clean_text (페이지 {i+1}): 페이지 번호 추정, 제거: '{line}'")
                continue
            # 숫자만 있는 줄 제거
            if re.match(r'^[\d\s\-\.]+$', line):
                 logger.debug(f"clean_text (페이지 {i+1}): 숫자만 있는 줄 제거: '{line}'")
                 continue
            # 특수 문자로만 이루어진 줄 제거
            if re.match(r'^[^\w\s가-힣]+$', line):
                 logger.debug(f"clean_text (페이지 {i+1}): 특수 문자만 있는 줄 제거: '{line}'")
                 continue

            # 짧은 줄 처리 (is_evidence 여부에 따라 기준 다름)
            min_len = 5 if is_evidence else 3
            if len(line) < min_len and not re.search(r'[가-힣]', line):
                 logger.debug(f"clean_text (페이지 {i+1}): 짧고 의미 없는 줄 제거: '{line}'")
                 continue

            # 불필요한 시작 기호 제거 (is_evidence 또는 목차 번호 아닌 경우)
            if is_evidence or not re.match(r'^\s*\d+[\.\s]', line):
                line = re.sub(r'^\s*[\*\-\•\◦\‣\▪\▫\□\■\◆\◇\○\●\-]+\s*', '', line)

            # 줄 끝 불필요한 문자 제거
            line = re.sub(r'[\-\,\:\;]+$', '', line)

            meaningful_lines.append(line)

        # 2단계: 문장 중간 줄바꿈 연결
        j = 0
        while j < len(meaningful_lines) - 1:
            current_line = meaningful_lines[j]
            next_line = meaningful_lines[j + 1]

            # 다음 줄이 목차 번호로 시작하면 연결 안 함
            if not is_evidence and re.match(r'^\s*\d+[\.\s]', next_line):
                j += 1
                continue

            # 현재 줄이 문장 중간에서 끝나는지 확인
            ends_like_sentence_end = re.search(r'[.?!]\s*$', current_line) if not is_evidence else re.search(r'[.?!,;:]\s*$', current_line)
            next_starts_like_new_sentence = re.match(r'^\d+[\.\)\s]', next_line)

            if current_line and not ends_like_sentence_end and next_line and not next_starts_like_new_sentence:
                meaningful_lines[j] = current_line + ' ' + next_line
                meaningful_lines.pop(j + 1)
                logger.debug(f"clean_text (페이지 {i+1}): 줄 연결 -> '{meaningful_lines[j][:80]}...'")
            else:
                j += 1

        # 3단계: 최종 정리 (중복 공백 제거)
        for line in meaningful_lines:
            line = re.sub(r'\s+', ' ', line).strip()
            if line:
                processed_lines.append(line)

        # 페이지 내용 결합 (is_evidence 여부에 따라 줄 간격 다름)
        cleaned_page_content = ('\n\n' if is_evidence else '\n').join(processed_lines)
        logger.debug(f"clean_text: 페이지 {i+1} 정리 완료. 길이: {len(cleaned_page_content)}")
        cleaned_pages.append(cleaned_page_content)

    # 정리된 페이지들을 원본 페이지 구분자로 다시 결합
    final_text = original_separator.join(cleaned_pages)
    logger.info(f"텍스트 정리 완료 (is_evidence={is_evidence}). 최종 길이: {len(final_text)}")
    return final_text


# 마크다운 생성 (step5_casefiles_extractor.py 로직 통합)
def create_markdown_output(text, original_file_path, output_folder_path, config, page_count=0, file_type=None):
    """
    추출된 텍스트로 마크다운 파일 생성 (파일 유형별 템플릿 및 페이지 마커 적용)

    :param text: 정리된 텍스트 (페이지 구분자 포함)
    :param original_file_path: 원본 파일 경로
    :param output_folder_path: 마크다운 파일 저장 폴더
    :param config: 설정 객체
    :param page_count: 총 페이지 수
    :param file_type: 파일 유형 ('evidence', 'submission', 'judgment', None)
    :return: 생성된 마크다운 파일 경로 또는 None
    """
    filename = os.path.basename(original_file_path)
    file_base, _ = os.path.splitext(filename)
    md_filename = f"{file_base}.md"
    md_filepath = os.path.join(output_folder_path, md_filename)
    logger.info(f"마크다운 생성 시도: '{md_filepath}' (유형: {file_type}, 총 {page_count} 페이지)")

    # --- 파일 존재 시 타임스탬프 추가 로직 (기존과 동일) ---
    counter = 0
    base_name = file_base
    while os.path.exists(md_filepath):
        counter += 1
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
        unique_md_filename = f"{base_name}_{timestamp}_{counter}.md"
        unique_md_filepath = os.path.join(output_folder_path, unique_md_filename)
        logger.warning(f"마크다운 파일 충돌: '{os.path.basename(md_filepath)}'. 새 이름 시도: '{unique_md_filename}'")
        md_filepath = unique_md_filepath
        if counter > 10:
            logger.error(f"고유 마크다운 파일명 생성 실패 (충돌 지속): {base_name}")
            print_message(f"오류: 고유한 마크다운 파일 이름 생성 실패. '{output_folder_path}' 확인 필요.", "error")
            return None
    if counter > 0:
        print_message(f"정보: 기존 마크다운 파일과 충돌하여 새 이름으로 저장 -> [filename_new]{os.path.basename(md_filepath)}[/]", "warning")
    # ---

    # --- 템플릿 가져오기 및 메타데이터 준비 (step5 로직) ---
    template_str = get_markdown_template(file_type, config, filename, original_file_path)
    if not template_str:
        logger.error(f"파일 유형 '{file_type}'에 대한 마크다운 템플릿을 찾을 수 없습니다.")
        print_message(f"오류: '{filename}'에 대한 마크다운 템플릿 로드 실패.", "error")
        return None

    # --- 페이지 마커 추가 로직 (파일 유형별 분기) ---
    formatted_text_for_md = ""
    if text and page_count > 0:
        pages_content = text.split("\n\n--- Page Break ---\n\n")
        actual_pages_for_marking = len(pages_content)
        if actual_pages_for_marking != page_count:
             logger.warning(f"페이지 수 불일치 경고: 계산된 페이지 수({page_count})와 분리된 페이지 수({actual_pages_for_marking})가 다릅니다. ('{filename}')")

        formatted_pages_list = []
        is_evidence = (file_type == 'evidence')

        for i, page_content in enumerate(pages_content):
            page_num = i + 1
            # 파일 유형에 따라 다른 페이지 마커 적용
            if is_evidence:
                # 7번 제출증거: 더 압축된 형식
                page_marker = f'**<span style="color:blue; background-color:#E6F7FF;">Page {page_num}/{actual_pages_for_marking}</span>**'
                separator = "\n\n" # 페이지 간 간격
            else:
                # 8번 제출서면 등: 기존 형식
                page_marker = f'***<span style="color:blue; background-color:#A6F1E0;"><big>[Page {page_num}/{actual_pages_for_marking}]</big></span>***'
                separator = "\n\n---\n\n" # 페이지 구분선 및 간격

            # 첫 페이지가 아니면 구분자 추가
            prefix = separator if i > 0 else ""
            formatted_pages_list.append(f"{prefix}{page_marker}\n\n{page_content.strip()}")

        formatted_text_for_md = "".join(formatted_pages_list) # 페이지 간 구분자는 이미 포함됨

    elif text:
         formatted_text_for_md = text # 페이지 1개 또는 0개
         logger.info(f"페이지 수가 1 이하이므로 페이지 마커를 추가하지 않음: '{filename}'")
    else:
        formatted_text_for_md = "*추출된 텍스트가 없습니다.*"
    # --- 페이지 마커 추가 로직 끝 ---

    # 메타데이터 구성 (step5 로직 통합)
    metadata = {
        'filename': file_base,
        'pdf_name_without_ext': file_base,
        'filename_base': file_base, # 호환성
        'filename_original': filename, # 호환성
        'pdf_path': original_file_path,
        'original_file': original_file_path,
        'original_file_path': original_file_path,
        'original_file_name': filename,
        'extraction_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'created_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), # 호환성
        'datetime': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'page_count': page_count,
        'total_pages': page_count,
        '총페이지수': page_count, # 호환성
        'content': formatted_text_for_md,
        'file_type_tag': file_type if file_type else 'Unknown', # 호환성
        # 파일명 기반 추가 메타데이터 (step5 로직)
        'date': '',
        'document_type': '',
        'submitter': '',
        'evidence_date': '',
        'evidence_type': '',
    }

    # 파일명에서 추가 정보 추출 시도
    try:
        parts = file_base.split('_')
        if len(parts) >= 3:
            date_part = next((p for p in parts if p.count('.') >= 2), '')
            if date_part: metadata['date'] = date_part

            if file_type == 'submission':
                doc_type = parts[-2] if len(parts) >= 4 else ''
                submitter = parts[-1] if len(parts) >= 4 else ''
                if doc_type: metadata['document_type'] = doc_type
                if submitter: metadata['submitter'] = submitter
            elif file_type == 'evidence':
                if date_part: metadata['evidence_date'] = date_part
                evidence_type = parts[-2] if len(parts) >= 4 else ''
                submitter = parts[-1] if len(parts) >= 4 else ''
                if evidence_type: metadata['evidence_type'] = evidence_type
                if submitter: metadata['submitter'] = submitter
    except Exception as e:
        logger.warning(f"파일명에서 메타데이터 추출 중 오류 ('{filename}'): {e}")

    # 마크다운 내용 생성 (템플릿 포맷팅)
    try:
        # 템플릿 내 모든 플레이스홀더 치환 시도
        final_content = template_str
        for key, value in metadata.items():
            placeholder = f"{{{key}}}"
            # 값이 비어있더라도 플레이스홀더는 제거 (빈 문자열로 치환)
            final_content = final_content.replace(placeholder, str(value) if value is not None else "")

        # 혹시 치환되지 않은 플레이스홀더가 있는지 확인 (오류 방지)
        remaining_placeholders = re.findall(r'\{[^{}]+\}', final_content)
        if remaining_placeholders:
            logger.warning(f"마크다운 생성 후에도 치환되지 않은 플레이스홀더 발견: {remaining_placeholders} in '{filename}'")
            # 치환 안된 플레이스홀더는 제거하거나 경고 표시 추가 가능
            # final_content = re.sub(r'\{[^{}]+\}', '', final_content) # 예: 제거

    except Exception as e:
        logger.error(f"마크다운 템플릿 포맷팅 중 오류 ('{filename}'): {e}", exc_info=True)
        print_message(f"오류: 마크다운 템플릿 생성 중 문제 발생 - {e}", "error")
        return None

    # 파일 저장 로직 (기존과 동일)
    try:
        with open(md_filepath, 'w', encoding='utf-8') as f:
            f.write(final_content)
        logger.info(f"마크다운 파일 생성 완료: {md_filepath}")
        placeholder_text = "*추출된 텍스트가 없습니다.*"
        if not formatted_text_for_md or formatted_text_for_md == placeholder_text or len(formatted_text_for_md) < 100:
            print_message(f"경고: 생성된 마크다운 파일 '[filename_new]{os.path.basename(md_filepath)}[/]'의 내용이 매우 짧거나 없습니다.", "warning")
        return md_filepath
    except IOError as e:
        logger.error(f"마크다운 파일 쓰기 오류: {md_filepath} - {e}", exc_info=True)
        print_message(f"오류: 마크다운 파일 저장 실패 - {e}", "error")
        return None
    except Exception as e:
        logger.error(f"마크다운 생성 중 알 수 없는 오류: {md_filepath} - {e}", exc_info=True)
        print_message(f"오류: 마크다운 파일 생성 중 문제 발생 - {e}", "error")
        return None
    
# 단일 파일 처리 함수 (step5 로직 통합)
def process_single_file(file_path, config):
    """단일 PDF 또는 이미지 파일 처리 (파일 유형 결정 및 전달)"""
    start_time = time.time()
    filename = os.path.basename(file_path)
    file_dir = os.path.dirname(file_path)
    logger.info(f"--- 파일 처리 시작: '{filename}' ---")

    ocr_config = config.get('text_extraction', {})
    poppler_path_from_config = config.get('external_tools', {}).get('poppler_path')
    language_hints = ocr_config.get('ocr_language_hints', ['ko', 'en'])
    credentials_path = ocr_config.get('google_credentials_path', '')

    if not credentials_path or not os.path.exists(credentials_path):
        print_message(f"오류: '{filename}' 처리 불가 - Google Cloud 인증 파일 문제.", "error")
        logger.error(f"인증 파일 문제로 '{filename}' 처리 중단: {credentials_path}")
        return None

    extracted_text = None
    page_count = 0
    file_ext = os.path.splitext(filename)[1].lower()
    supported_images = ['.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp']
    images = None
    results = None

    # --- 파일 유형 결정 (step5 로직) ---
    file_type = determine_file_type(filename, config)
    logger.info(f"파일 유형 결정: '{filename}' -> {file_type}")
    is_evidence = (file_type == 'evidence') # 텍스트 정리 및 마커 형식에 사용

    try:
        # 1. 텍스트 추출
        if file_ext == '.pdf':
            print_message(f"PDF 파일 처리 중: [filename_original]{filename}[/] (유형: {file_type})...", "info")
            dpi = ocr_config.get('ocr_dpi', 300)
            images = convert_pdf_to_images(file_path, dpi, poppler_path_from_config)

            if not images:
                print_message(f"오류: '{filename}' PDF 이미지 변환 실패.", "error")
                return None

            page_count = len(images)
            logger.info(f"PDF에서 {page_count} 페이지 감지. OCR 시작...")

            page_texts = [""] * page_count
            # 병렬 처리 워커 수 설정 (config 우선, 없으면 기본값)
            max_workers_ocr = ocr_config.get('max_workers', min(4, os.cpu_count() or 1))
            with ThreadPoolExecutor(max_workers=max_workers_ocr) as executor:
                image_data_list = [(i, img, language_hints, credentials_path) for i, img in enumerate(images)]
                futures = [executor.submit(detect_text_from_image, image_data) for image_data in image_data_list]

                results = {}
                for future in as_completed(futures):
                    try:
                        idx, text_result = future.result()
                        results[idx] = text_result
                    except Exception as e:
                        logger.error(f"텍스트 추출 작업 Future 처리 중 오류: {e}", exc_info=True)
                        # 오류 발생 페이지는 detect_text_from_image 에서 오류 문자열 반환

                final_page_texts = []
                for i in range(page_count):
                     page_text = results.get(i, f"*** 페이지 {i+1} 결과 처리 오류 ***")
                     final_page_texts.append(page_text)
                     if i < page_count - 1:
                          final_page_texts.append("--- Page Break ---") # 페이지 구분자 추가

            extracted_text = "\n\n".join(final_page_texts)

        elif file_ext in supported_images:
            print_message(f"이미지 파일 처리 중: [filename_original]{filename}[/] (유형: {file_type})...", "info")
            page_count = 1
            try:
                with Image.open(file_path) as img:
                    _, extracted_text = detect_text_from_image((0, img, language_hints, credentials_path))
                    if extracted_text is not None:
                        extracted_text = extracted_text.replace("\n\n--- Page Break ---\n\n", "\n\n").strip()
            except UnidentifiedImageError:
                print_message(f"오류: '{filename}'은(는) 유효한 이미지 파일이 아닙니다.", "error")
                logger.error(f"유효하지 않은 이미지 파일: {filename}", exc_info=True)
                return None # 처리 중단
            except Exception as img_e:
                print_message(f"오류: 이미지 파일 '{filename}' 처리 중 문제 발생 - {img_e}", "error")
                logger.error(f"이미지 처리 오류: {filename} - {img_e}", exc_info=True)
                return None # 처리 중단
        else:
            print_message(f"정보: 지원되지 않는 파일 형식입니다: [filename_original]{filename}[/]. 건너뜁니다.", "skipped")
            logger.info(f"지원하지 않는 파일 형식 건너뜁니다: {filename}")
            return None

        # 추출 실패 또는 오류 문자열 포함 시 경고
        if extracted_text is None:
             logger.error(f"'{filename}'에서 텍스트 추출 실패 (extracted_text is None).")
             return None
        elif not extracted_text.strip() or "***" in extracted_text:
            print_message(f"경고: '{filename}'에서 텍스트를 성공적으로 추출하지 못했거나 오류 문자열을 포함합니다.", "warning")
            # 오류가 있더라도 마크다운 생성 시도

        # 2. 텍스트 정리 (파일 유형 정보 전달)
        logger.info(f"텍스트 정리 작업 시작 (is_evidence={is_evidence})...")
        cleaned_text = clean_text(extracted_text, is_evidence=is_evidence)

        # 3. 마크다운 생성 (페이지 수 및 파일 유형 정보 전달)
        logger.info(f"마크다운 파일 생성 시작... (페이지 수: {page_count}, 유형: {file_type})")
        md_filepath = create_markdown_output(
            cleaned_text,
            file_path,
            file_dir,
            config,
            page_count=page_count,
            file_type=file_type # 파일 유형 전달
        )

        total_time = time.time() - start_time
        if md_filepath:
            logger.info(f"--- 파일 처리 완료: '{filename}' -> '{os.path.basename(md_filepath)}' (총 {total_time:.2f}초) ---")
            return md_filepath
        else:
            logger.error(f"--- 파일 처리 실패 (마크다운 생성 실패): '{filename}' (총 {total_time:.2f}초) ---")
            return None

    except Exception as e:
        logger.error(f"--- 파일 처리 중 예외 발생: '{filename}' - {e} ---", exc_info=True)
        print_message(f"오류: '{filename}' 처리 중 예기치 않은 문제 발생 - {e}", "error")
        return None


# 폴더 처리 함수 (수정됨: <0xEB><0x9B><0x84> 수정)
def process_folder(target_folder, config):
    """지정된 폴더 내의 모든 PDF 및 지원되는 이미지 파일 처리"""
    if not target_folder or not os.path.isdir(target_folder):
        print_message(f"오류: 유효하지 않은 폴더 경로입니다 - '{target_folder}'", "error")
        return

    print_message(f"폴더 처리 시작: [path]{target_folder}[/]", "phase")
    files_to_process = []
    supported_extensions = ['.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp']

    # 처리 대상 파일 스캔
    try:
        for filename in os.listdir(target_folder):
            file_path = os.path.join(target_folder, filename)
            if os.path.isfile(file_path):
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in supported_extensions:
                    files_to_process.append(file_path)
                else:
                    logger.debug(f"지원하지 않는 확장자 건너뜁니다: {filename}") # 수정됨
    except Exception as e:
        print_message(f"오류: 폴더 스캔 중 문제 발생 - {e}", "error")
        logger.error(f"폴더 스캔 오류: {target_folder} - {e}", exc_info=True)
        return

    if not files_to_process:
        print_message("정보: 해당 폴더에 처리할 PDF 또는 이미지 파일이 없습니다.", "warning")
        return

    print_message(f"총 {len(files_to_process)}개의 처리 대상 파일 발견.", "info")

    # 병렬 처리 실행
    max_workers = min(8, (os.cpu_count() or 1) + 4) # I/O bound 고려하여 워커 수 조정
    successful_files = []
    failed_files = []

    # Rich Progress 사용 설정
    progress_context = None
    task_id = None
    if RICH_AVAILABLE:
        progress_context = Progress(
            SpinnerColumn(), # 스피너 추가
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeRemainingColumn(), # 남은 시간 추가
            TextColumn("[info]{task.completed} / {task.total} 파일 처리됨[/]"),
            console=console,
            transient=False # 완료 후에도 표시 유지
        )
        task_id = progress_context.add_task("[cyan]파일 처리 중...", total=len(files_to_process))
        progress_context.start()

    try:
        # ThreadPoolExecutor 사용 (OCR API 호출 등 I/O 작업에 유리)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 각 파일 처리를 위한 future 생성 (config 객체 전달)
            future_to_file = {executor.submit(process_single_file, file_path, config): file_path for file_path in files_to_process}

            for future in as_completed(future_to_file):
                original_path = future_to_file[future]
                original_filename = os.path.basename(original_path)
                try:
                    result_path = future.result() # process_single_file의 반환값
                    if result_path:
                        successful_files.append(os.path.basename(result_path))
                    else:
                        # process_single_file 내부에서 None 반환 시 실패 처리
                        failed_files.append(original_filename)
                        # 실패 이유는 이미 process_single_file 또는 create_markdown_output 에서 로깅됨
                except Exception as exc:
                    # future.result() 자체에서 예외 발생 시 (매우 드문 경우)
                    failed_files.append(original_filename)
                    logger.error(f"파일 처리 Future 결과 가져오는 중 심각한 오류: '{original_filename}' - {exc}", exc_info=True)
                    print_message(f"오류: '{original_filename}' 처리 중 예상치 못한 심각한 문제 발생.", "error")
                finally:
                    if RICH_AVAILABLE and task_id is not None:
                        progress_context.update(task_id, advance=1) # 작업 완료 시 진행률 업데이트

    finally: # 작업 완료 후 Progress 중지
        if RICH_AVAILABLE and progress_context:
            progress_context.stop()

    # 최종 결과 요약 출력
    print_message("\n--- 처리 결과 요약 ---", "phase")
    print_message(f"성공: {len(successful_files)}개 파일", "success")
    print_message(f"실패: {len(failed_files)}개 파일", "error" if failed_files else "info")
    if failed_files:
        print_message("실패한 파일 목록:", "warning")
        # 실패 목록은 최대 10개까지만 출력 (너무 많으면 생략)
        for i, fname in enumerate(failed_files):
            if i < 10:
                print_message(f"- [filename_original]{fname}[/]", "warning")
            elif i == 10:
                print_message("- ... (더 많은 파일은 로그 확인)", "warning")
                break
        print_message("상세 내용은 로그 파일을 확인하십시오.", "warning")

# --- Helper 함수 (step5 에서 가져옴) ---
def extract_prefix_from_filename(filename):
    """
    파일명에서 접두어 추출 (예: '7_제출증거_', '8_제출서면_', '9_판결_')
    """
    prefix_pattern = re.compile(r'^(\d+_[^_]+)_')
    match = prefix_pattern.search(filename)
    return match.group(1) if match else None

def determine_file_type(filename, config):
    """
    파일명 패턴 매칭을 통한 유형 분류 (step5 로직)
    """
    evidence_patterns = config.get('text_extraction', {}).get('evidence_template', {}).get('patterns', [])
    submission_patterns = config.get('text_extraction', {}).get('submission_template', {}).get('patterns', [])
    judgment_patterns = config.get('text_extraction', {}).get('judgment_template', {}).get('patterns', [])

    for pattern in evidence_patterns:
        if re.search(pattern, filename): return 'evidence'
    for pattern in submission_patterns:
        if re.search(pattern, filename): return 'submission'
    for pattern in judgment_patterns:
        if re.search(pattern, filename): return 'judgment'

    # 파일명 규칙 패턴 확인 (config.yaml 의 file_naming_rules)
    file_naming_rules = config.get('file_naming_rules', {}).get('prefix_patterns', {})
    for prefix, patterns in file_naming_rules.items():
        if prefix.startswith("7_제출증거_") and any(re.search(p, filename) for p in patterns if p): return 'evidence'
        elif prefix.startswith("8_제출서면_") and any(re.search(p, filename) for p in patterns if p): return 'submission'
        elif prefix.startswith("9_판결_") and any(re.search(p, filename) for p in patterns if p): return 'judgment'

    logger.debug(f"파일 유형을 결정할 수 없음: '{filename}'. 기본 템플릿 사용 예정.")
    return None # 기본값 또는 'unknown' 등 반환 가능

def get_markdown_template(file_type, config, filename, pdf_path):
    """
    파일 유형에 맞는 마크다운 템플릿 반환 (step5 로직)
    """
    template_config = config.get('text_extraction', {})
    default_template_str = config.get('default_template', {}).get('metadata_template', '')

    if file_type == 'evidence':
        template_str = template_config.get('evidence_template', {}).get('metadata_template', default_template_str)
    elif file_type == 'submission':
        template_str = template_config.get('submission_template', {}).get('metadata_template', default_template_str)
    elif file_type == 'judgment':
        template_str = template_config.get('judgment_template', {}).get('metadata_template', default_template_str)
    else: # None 또는 알 수 없는 유형
        template_str = default_template_str

    if not template_str:
        logger.warning(f"'{filename}' (유형: {file_type})에 대한 마크다운 템플릿 문자열이 비어있습니다. 기본 템플릿 사용.")
        # 매우 기본적인 폴백 템플릿
        template_str = """---
tags: [텍스트추출, {file_type_tag}]
문서명: {filename_base}
원본파일: "[[{filename_original}]]"
총페이지수: {total_pages}
추출일시: {extraction_date}
---

# {filename_base}

## 추출된 텍스트

{content}
"""
    # 템플릿 반환 (변수 치환은 create_markdown_output 에서 수행)
    return template_str

# --- 메인 실행 ---
def main():
    """스크립트 메인 함수"""
    parser = argparse.ArgumentParser(
        description='지정된 폴더 내 PDF 및 이미지 파일에서 텍스트를 추출하여 마크다운으로 저장합니다.',
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('target_folder', nargs='?', default=None,
                        help='텍스트를 추출할 파일들이 있는 폴더 경로 (생략 시 입력 요청)')
    parser.add_argument('--config', '-c', default='config.yaml',
                        help='사용자 설정 파일 경로 (기본값: config.yaml)')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                        help='로그 상세 수준 설정 (기본값: INFO)')
    parser.add_argument('--log-file', default=None,
                        help='로그를 기록할 파일 경로 (기본값: logs/general_extractor.log)')

    args = parser.parse_args()

    # --- 로거 및 설정 초기화 ---
    # 로그 파일 경로 결정 (기본값 설정 포함)
    default_log_config = create_default_config().get('logging', {})
    log_dir_from_config = default_log_config.get('log_dir', 'logs')
    log_file_from_config = default_log_config.get('file', 'general_extractor.log')

    # 명령줄 인수가 있으면 우선 사용, 없으면 설정값 사용
    final_log_file_path = args.log_file
    if not final_log_file_path:
        # 기본 로그 디렉토리/파일 경로 조합 (현재 작업 디렉토리 기준)
        log_dir = log_dir_from_config
        if not os.path.isabs(log_dir):
            log_dir = os.path.join(os.getcwd(), log_dir)
        final_log_file_path = os.path.join(log_dir, log_file_from_config)
    else:
        # 제공된 경로가 상대 경로면 절대 경로로 변환
        if not os.path.isabs(final_log_file_path):
            final_log_file_path = os.path.join(os.getcwd(), final_log_file_path)
        # 디렉토리 경로 확보
        log_dir = os.path.dirname(final_log_file_path)

    # 로그 디렉토리 생성 (필요시)
    if log_dir and not os.path.exists(log_dir):
         try:
              os.makedirs(log_dir)
         except OSError as e:
              print(f"경고: 로그 디렉토리 생성 실패 '{log_dir}' - {e}")
              final_log_file_path = None # 파일 로깅 비활성화

    # 로깅 설정 적용
    setup_logging(args.log_level, final_log_file_path)

    # 설정 로드 및 병합
    user_config = load_config(args.config)
    config = merge_configs(create_default_config(), user_config)
    # 병합 후 로깅 레벨 재설정 (사용자 설정 우선)
    final_log_level = config.get('logging', {}).get('level', args.log_level).upper()
    if final_log_level != args.log_level.upper():
        logger.info(f"설정 파일에 따라 로그 레벨 변경: {final_log_level}")
        setup_logging(final_log_level, final_log_file_path) # 로거 재설정

    logger.debug(f"명령줄 인수: {args}")
    logger.info(f"텍스트 추출기 시작. 로그 레벨: {final_log_level}")
    # 사용될 Poppler 경로 로깅
    poppler_check = config.get('external_tools', {}).get('poppler_path') or '시스템 PATH'
    logger.info(f"사용될 Poppler 경로: {poppler_check}")
    # 사용될 Google Credentials 경로 로깅
    creds_check = config.get('text_extraction', {}).get('google_credentials_path')
    logger.info(f"사용될 Google Credentials 경로: {creds_check if creds_check else '설정되지 않음'}")


    # --- 대상 폴더 경로 확인 ---
    target_folder_path = args.target_folder
    if not target_folder_path:
        prompt = "[question]텍스트를 추출할 폴더 경로를 입력하세요:[/]"
        try:
            if RICH_AVAILABLE:
                target_folder_path = console.input(prompt)
            else:
                target_folder_path = input("텍스트를 추출할 폴더 경로를 입력하세요: ")
            target_folder_path = target_folder_path.strip().strip('"\'') # 따옴표 제거 추가
            if not target_folder_path:
                print_message("오류: 폴더 경로가 입력되지 않았습니다.", "error")
                sys.exit(1)
        except (EOFError, KeyboardInterrupt):
            print_message("\n입력 취소. 스크립트를 종료합니다.", "warning")
            sys.exit(0)

    # 입력받은 경로 정규화 및 절대 경로 변환
    target_folder_path = os.path.normpath(os.path.abspath(target_folder_path))
    logger.info(f"처리 대상 폴더: {target_folder_path}")

    # --- 폴더 처리 실행 ---
    process_folder(target_folder_path, config)

    print_message("\n모든 작업 완료.", "phase")
    logger.info("텍스트 추출 작업 완료.")

if __name__ == "__main__":
    # 메인 함수 실행 전 기본 로거 설정 (핸들러 없을 경우 대비)
    if not logger.hasHandlers():
        setup_logging() # 기본 설정으로 초기화
        logger.info("기본 로거 초기화 완료 (__main__ 가드)")
    main()