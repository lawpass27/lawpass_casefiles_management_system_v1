# -*- coding: utf-8 -*-
"""
전자소송 파일 이름 변경 모듈
"""
import os
import re
import sys
import argparse
import logging
from datetime import datetime
import yaml

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

# Rich 콘솔 객체 생성
custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "phase": "bold blue",
    "filename": "italic yellow",
    "newname": "italic green",
})

console = Console(theme=custom_theme) if RICH_AVAILABLE else None

# 로깅 설정 함수
def setup_logging(level="INFO", log_file=None):
    """로깅 설정"""
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    # 로그 포맷 설정
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    
    # 로거 설정
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    
    # 기존 핸들러 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Rich 로깅 핸들러 추가 (사용 가능한 경우)
    if RICH_AVAILABLE:
        rich_handler = RichHandler(rich_tracebacks=True, markup=True)
        rich_handler.setLevel(numeric_level)
        logger.addHandler(rich_handler)
    else:
        # 콘솔 핸들러 추가
        console_handler = logging.StreamHandler()
        console_handler.setLevel(numeric_level)
        formatter = logging.Formatter(log_format, date_format)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 파일 핸들러 추가 (로그 파일이 지정된 경우)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(numeric_level)
        formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

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
    case_folder = input("사건 폴더 경로를 입력하세요: ")
    # 따옴표 제거
    case_folder = case_folder.strip('"\'')
    return os.path.normpath(case_folder)

# 파일명 분석 함수
def parse_filename(filename, config=None):
    """원본 파일명 분석"""
    # 설정 파일에서 패턴 가져오기
    prefix_patterns = {}
    if config and 'file_naming_rules' in config and 'prefix_patterns' in config['file_naming_rules']:
        prefix_patterns = config['file_naming_rules']['prefix_patterns']
    
    # 기본 패턴 (사건번호_날짜_문서종류_...)
    pattern = r"(\d+[가-힣]+\d+)_(\d{4}\.\d{2}\.\d{2})_([^_]+)_?(.*)"
    match = re.match(pattern, filename)
    
    if match:
        case_number = match.group(1)
        date = match.group(2)
        doc_type = match.group(3)
        rest = match.group(4)
        
        # 파일 유형에 따라 적절한 변환 함수 호출
        new_filename = None
        
        # 갑/을 증거 파일 확인
        if is_evidence_file(filename, prefix_patterns):
            new_filename = rename_evidence_file(filename)
        
        # 사실조회 회신서 확인
        elif is_fact_inquiry_response(filename, prefix_patterns):
            new_filename = rename_fact_inquiry_response(filename)
        
        # 증인신문조서 확인
        elif is_witness_file(filename, prefix_patterns):
            new_filename = rename_witness_file(filename)
        
        # 녹취서 확인
        elif is_transcript_file(filename, prefix_patterns):
            new_filename = rename_transcript_file(filename)
        
        # 증인 신문사항 확인
        elif is_witness_question_file(filename, prefix_patterns):
            new_filename = rename_witness_question_file(filename)
        
        # 항소이유서 확인 (판결문보다 먼저 확인)
        elif is_appeal_reason_file(filename, prefix_patterns):
            new_filename = rename_appeal_reason_file(filename)
        
        # 판결문 확인
        elif is_judgment_file(filename, prefix_patterns):
            new_filename = rename_judgment_file(filename)
        
        # 판결선고조서 확인
        elif is_judgment_declaration_file(filename, prefix_patterns):
            new_filename = rename_judgment_declaration_file(filename)
        
        # 소송 서류 확인 (판결선고조서 포함)
        elif is_document_type(filename, prefix_patterns):
            new_filename = rename_document_file(filename)
        
        # 변환 함수가 적절한 결과를 반환하지 않은 경우 원본 파일명 유지
        if not new_filename:
            new_filename = filename
            
        return {
            "case_number": case_number,
            "date": date,
            "doc_type": doc_type,
            "rest": rest,
            "new_filename": new_filename
        }
    return None

def get_patterns_for_prefix(prefix, prefix_patterns):
    """특정 접두어에 대한 패턴 목록 가져오기"""
    if not prefix_patterns or prefix not in prefix_patterns:
        # 설정 파일에서 패턴을 찾을 수 없는 경우 빈 리스트 반환
        logging.warning(f"설정 파일에서 '{prefix}' 접두어에 대한 패턴을 찾을 수 없습니다.")
        return []
    
    return prefix_patterns[prefix]

def is_evidence_file(filename, prefix_patterns):
    """파일이 갑/을 증거 파일인지 확인"""
    evidence_patterns = get_patterns_for_prefix("7_제출증거_", prefix_patterns)
    for pattern in evidence_patterns:
        if (pattern.startswith("갑") or pattern.startswith("을")) and re.search(pattern, filename):
            return True
    return False

def is_fact_inquiry_response(filename, prefix_patterns):
    """파일이 사실조회 회신서인지 확인"""
    evidence_patterns = get_patterns_for_prefix("7_제출증거_", prefix_patterns)
    
    # 7_제출증거_ 패턴에서만 사실조회 회신서 확인
    return ("사실조회 회신" in filename or "사실조회회신" in filename) and (
        any("사실조회 회신" in pattern for pattern in evidence_patterns) or
        any("사실조회회신" in pattern for pattern in evidence_patterns)
    )

def is_witness_file(filename, prefix_patterns):
    """파일이 증인신문조서인지 확인"""
    evidence_patterns = get_patterns_for_prefix("7_제출증거_", prefix_patterns)
    return "증인신문조서" in filename and any("증인신문조서" in pattern for pattern in evidence_patterns)

def is_transcript_file(filename, prefix_patterns):
    """파일이 녹취서인지 확인"""
    evidence_patterns = get_patterns_for_prefix("7_제출증거_", prefix_patterns)
    return "녹취서" in filename and any("녹취서" in pattern for pattern in evidence_patterns)

def is_witness_question_file(filename, prefix_patterns):
    """파일이 증인 신문사항인지 확인"""
    evidence_patterns = get_patterns_for_prefix("7_제출증거_", prefix_patterns)
    return ("증인 신문사항" in filename or "신문사항" in filename) and any("신문사항" in pattern for pattern in evidence_patterns)

def is_document_type(filename, prefix_patterns):
    """파일이 소송 서류 유형인지 확인"""
    # 8_제출서면_ 접두어에 해당하는 패턴 찾기
    document_patterns = get_patterns_for_prefix("8_제출서면_", prefix_patterns)
    
    # 각 문서 유형에 대해 확인
    for pattern in document_patterns:
        if pattern in filename and "첨부" not in filename and "서증" not in filename:
            return True
    
    # 판결선고조서 확인
    if "판결선고조서" in filename:
        return True
    
    return False

def is_judgment_file(filename, prefix_patterns):
    """파일이 판결문인지 확인"""
    judgment_patterns = get_patterns_for_prefix("9_판결_", prefix_patterns)
    return "판결문" in filename and any("판결문" in pattern for pattern in judgment_patterns)

def is_judgment_declaration_file(filename, prefix_patterns):
    """파일이 판결선고조서인지 확인"""
    document_patterns = get_patterns_for_prefix("8_제출서면_", prefix_patterns)
    return "판결선고조서" in filename

def is_appeal_reason_file(filename, prefix_patterns):
    """파일이 항소이유서인지 확인"""
    document_patterns = get_patterns_for_prefix("8_제출서면_", prefix_patterns)
    return "항소이유서" in filename and any("항소이유서" in pattern for pattern in document_patterns)

# 증거 파일(갑/을) 이름 변경
def rename_evidence_file(filename):
    """증거 파일(갑/을) 이름 변경"""
    # 갑/을 증거 번호 추출
    evidence_pattern = r"(갑|을)(\d+)(?:-(\d+))?"
    evidence_match = re.search(evidence_pattern, filename)
    
    if evidence_match:
        evidence_type = evidence_match.group(1)  # 갑 또는 을
        evidence_num = evidence_match.group(2)   # 번호
        evidence_sub = evidence_match.group(3)   # 하위 번호
        
        # 증거 번호 형식 생성
        if evidence_sub:
            evidence_number = f"({evidence_type}{evidence_num}-{evidence_sub})"
        else:
            evidence_number = f"({evidence_type}{evidence_num})"
        
        # 내용 설명 추출 - 더 완전한 설명을 위해 패턴 수정
        content_desc = ""
        
        # 갑/을 번호와 내용설명이 함께 있는 패턴 확인 (예: 갑8-1_등기사항전부증명서(토지))
        full_desc_pattern = r"(?:갑|을)\d+(?:-\d+)?_([^_]+)"
        full_desc_match = re.search(full_desc_pattern, filename)
        if full_desc_match:
            content_desc = full_desc_match.group(1)
        
        # 위 패턴으로 추출 실패시 괄호 내용 확인
        if not content_desc:
            # 괄호 안의 내용 추출 (첫 번째 괄호는 증거 번호일 수 있으므로 건너뛰기)
            content_pattern = r"\(([^()]+)\)"
            content_matches = re.findall(content_pattern, filename)
            
            for match in content_matches:
                if not re.match(r"(?:갑|을)\d+(?:-\d+)?", match) and not match.startswith("녹음파일"):
                    content_desc = match
                    break
        
        # 내용 설명이 여전히 없는 경우 파일명에서 추출 시도
        if not content_desc:
            parts = filename.split("_")
            for part in parts:
                if not re.match(r"(?:갑|을)\d+(?:-\d+)?", part) and part not in ["서증", "원고", "피고", "대리인"]:
                    content_desc = part
                    break
        
        # 내용 설명 가공 - 괄호 유지하도록 수정, 중복 제거
        if content_desc:
            # 특수문자 제거 (괄호는 유지)
            content_desc = re.sub(r"[^\w\s가-힣()]", "", content_desc)
            # 공백을 언더스코어로 변경
            content_desc = "_".join(content_desc.split())
            
            # 반복되는 문구 제거 (예: "등기사항전부증명서(법인))(등기사항전부증명서(법인))")
            # 괄호를 포함한 동일 문구가 반복되는 경우 처리
            repeat_pattern = r"([^()]+\([^()]+\))\)\((\1)"
            content_desc = re.sub(repeat_pattern, r"\1", content_desc)
            
            # 괄호 없이 동일 문구가 반복되는 경우 처리
            words = content_desc.split("_")
            unique_words = []
            for word in words:
                if word not in unique_words:
                    unique_words.append(word)
            content_desc = "_".join(unique_words)
        
        # 파일 확장자 추출
        ext = os.path.splitext(filename)[1]
        
        # 새 파일명 생성
        if content_desc:
            new_filename = f"{evidence_number}_{content_desc}{ext}"
        else:
            new_filename = f"{evidence_number}{ext}"
        
        return new_filename

    return None

# 사실조회 회신서 파일 이름 변경 함수 추가
def rename_fact_inquiry_response(filename):
    """사실조회 회신서 파일 이름 변경"""
    # 날짜 추출
    date_pattern = r"_(\d{4}\.\d{2}\.\d{2})_"
    date_match = re.search(date_pattern, filename)
    
    if date_match:
        date = date_match.group(1).replace(".", "").strip()
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        formatted_date = f"{year}.{month}.{day}"
        
        # 기타 정보 추출 (회신 기관 등)
        org_pattern = r"_기타_([^_]+)_"
        org_match = re.search(org_pattern, filename)
        org_name = ""
        if org_match:
            org_name = org_match.group(1)
        
        # 파일 확장자 추출
        ext = os.path.splitext(filename)[1]
        
        # 새 파일명 생성
        new_filename = f"{formatted_date}.자_사실조회회신서_기타"
        if org_name:
            new_filename += f"_{org_name}"
        new_filename += ext
        
        return new_filename
    
    return None

# 증인신문조서 파일 이름 변경
def rename_witness_file(filename):
    """증인신문조서 파일 이름 변경"""
    # 날짜 추출
    date_pattern = r"_(\d{4}\.\d{2}\.\d{2})_"
    date_match = re.search(date_pattern, filename)
    
    if date_match:
        date = date_match.group(1).replace(".", "").strip()
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        formatted_date = f"{year}.{month}.{day}"
        
        # 파일 확장자 추출
        ext = os.path.splitext(filename)[1]
        
        # 법정녹음 파일 확인
        if "법정녹음" in filename or ext.lower() == ".mp3":
            return f"{formatted_date}.자_증인신문조서_법정녹음{ext}"
        else:
            return f"{formatted_date}.자_증인신문조서{ext}"
    
    return None

# 녹취서 파일 이름 변경
def rename_transcript_file(filename):
    """녹취서 파일 이름 변경"""
    # 날짜 추출
    date_pattern = r"_(\d{4}\.\d{2}\.\d{2})_"
    date_match = re.search(date_pattern, filename)
    
    if date_match:
        date = date_match.group(1).replace(".", "").strip()
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        formatted_date = f"{year}.{month}.{day}"
        
        # 녹취서 내용 추출
        content_pattern = r"녹취서요지\(([^)]+)\)"
        content_match = re.search(content_pattern, filename)
        content = ""
        if content_match:
            content = f"(증인{content_match.group(1)})"
        else:
            # 괄호 안의 내용 추출 시도
            content_pattern = r"\(([^)]+)\)"
            content_match = re.search(content_pattern, filename)
            if content_match:
                content = f"({content_match.group(1)})"
        
        # 파일 확장자 추출
        ext = os.path.splitext(filename)[1]
        
        return f"{formatted_date}.자_녹취서요지{content}{ext}"
    
    return None

# 소송 서류 파일 이름 변경
def rename_document_file(filename):
    """소송 서류 파일 이름 변경"""
    # 첨부 또는 서증이 포함된 경우 제외 (이 함수에서만 적용)
    if "첨부" in filename or "서증" in filename:
        return None
    
    # 날짜 추출
    date_pattern = r"_(\d{4}\.\d{2}\.\d{2})_"
    date_match = re.search(date_pattern, filename)
    
    if date_match:
        date = date_match.group(1).replace(".", "").strip()
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        formatted_date = f"{year}.{month}.{day}"
        
        # 문서 종류 추출
        doc_types = ["항소장", "소장", "답변서", "준비서면", "신청서", "변론조서", "기일변경신청서"]
        doc_type = ""
        
        # 항소장 먼저 확인 (소장보다 우선순위 높게)
        if "항소장" in filename:
            doc_type = "항소장"
        else:
            for dt in doc_types:
                if dt in filename:
                    doc_type = dt
                    break
        
        # 추가 정보 추출 (변론조서 회차 등)
        additional_info = ""
        if "변론조서" in filename:
            round_pattern = r"변론조서 \((\d+)회\)"
            round_match = re.search(round_pattern, filename)
            if round_match:
                additional_info = f"({round_match.group(1)}회)"
        
        # 신청서 종류 추출
        if "신청서" in filename:
            # 특정 신청서 종류 먼저 확인
            if "청구취지변경" in filename:
                doc_type = "청구취지변경 신청서"
            elif "청구원인변경" in filename:
                doc_type = "청구원인변경 신청서"
            else:
                # 기존 정규표현식 패턴 사용
                app_pattern = r"([가-힣]+신청서)(?:\(([^)]+)\))?"
                app_match = re.search(app_pattern, filename)
                if app_match:
                    doc_type = app_match.group(1)
                    if app_match.group(2):
                        additional_info = f"({app_match.group(2)})"
        
        # 당사자 정보 추출
        party = ""
        if "원고" in filename:
            party = "원고"
        elif "피고" in filename:
            party = "피고"
        
        # 파일 확장자 추출
        ext = os.path.splitext(filename)[1]
        
        # 새 파일명 생성
        new_filename = f"{formatted_date}.자_{doc_type}{additional_info}"
        if party:
            new_filename += f"_{party}"
        new_filename += ext
        
        return new_filename
    
    return None

# 판결선고조서 파일 이름 변경
def rename_judgment_declaration_file(filename):
    """판결선고조서 파일 이름 변경"""
    # 날짜 추출
    date_pattern = r"_(\d{4}\.\d{2}\.\d{2})_"
    date_match = re.search(date_pattern, filename)
    
    if date_match:
        date = date_match.group(1).replace(".", "").strip()
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        formatted_date = f"{year}.{month}.{day}"
        
        # 파일 확장자 추출
        ext = os.path.splitext(filename)[1]
        
        return f"{formatted_date}.자_판결선고조서{ext}"
    
    return None

# 판결문 파일 이름 변경
def rename_judgment_file(filename):
    """판결문 파일 이름 변경"""
    # 날짜 추출
    date_pattern = r"_(\d{4}\.\d{2}\.\d{2})_"
    date_match = re.search(date_pattern, filename)
    
    if date_match:
        date = date_match.group(1).replace(".", "").strip()
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        formatted_date = f"{year}.{month}.{day}"
        
        # 판사 정보 추출
        party = ""
        if "판사" in filename:
            party = "판사"
            # 판사 이름 추출
            judge_pattern = r"판사_([^_]+)"
            judge_match = re.search(judge_pattern, filename)
            if judge_match:
                party = f"판사_{judge_match.group(1)}"
        
        # 파일 확장자 추출
        ext = os.path.splitext(filename)[1]
        
        # 새 파일명 생성
        new_filename = f"{formatted_date}.자_판결문"
        if party:
            new_filename += f"_{party}"
        new_filename += ext
        
        return new_filename
    
    return None

# 항소이유서 파일 이름 변경
def rename_appeal_reason_file(filename):
    """항소이유서 파일 이름 변경"""
    # 날짜 추출
    date_pattern = r"_(\d{4}\.\d{2}\.\d{2})_"
    date_match = re.search(date_pattern, filename)
    
    if date_match:
        date = date_match.group(1).replace(".", "").strip()
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        formatted_date = f"{year}.{month}.{day}"
        
        # 당사자 정보 추출
        party = ""
        if "원고" in filename:
            party = "원고"
        elif "피고" in filename:
            party = "피고"
        
        # 파일 확장자 추출
        ext = os.path.splitext(filename)[1]
        
        # 새 파일명 생성
        new_filename = f"{formatted_date}.자_항소이유서"
        if party:
            new_filename += f"_{party}"
        new_filename += ext
        
        return new_filename
    
    return None

# 증인 신문사항 파일 이름 변경
def rename_witness_question_file(filename):
    """증인 신문사항 파일 이름 변경"""
    # 날짜 추출
    date_pattern = r"_(\d{4}\.\d{2}\.\d{2})_"
    date_match = re.search(date_pattern, filename)
    
    if date_match:
        date = date_match.group(1).replace(".", "").strip()
        year = date[:4]
        month = date[4:6]
        day = date[6:8]
        formatted_date = f"{year}.{month}.{day}"
        
        # 증인 이름 추출
        witness_pattern = r"증인신청서\(([^)]+)\)"
        witness_match = re.search(witness_pattern, filename)
        witness = ""
        if witness_match:
            witness = f"({witness_match.group(1)})"
        
        # 당사자 정보 추출
        party = ""
        if "원고" in filename:
            party = "원고"
        elif "피고" in filename or "법무법인 진심" in filename:
            party = "피고"
        
        # 파일 확장자 추출
        ext = os.path.splitext(filename)[1]
        
        # 새 파일명 생성
        new_filename = f"{formatted_date}.자_증인신문사항{witness}"
        if party:
            new_filename += f"_{party}"
        new_filename += ext
        
        return new_filename
    
    return None

# 파일 이름 변경 실행
def rename_files(case_folder, original_folder_name="원본폴더", config=None):
    """파일 이름 변경 실행"""
    # 원본 폴더 경로
    original_folder = os.path.join(case_folder, original_folder_name)
    
    # 사건 폴더가 존재하는지 확인
    if not os.path.exists(case_folder):
        logging.error(f"사건 폴더가 존재하지 않습니다: {case_folder}")
        return 0, [], [f"사건 폴더가 존재하지 않습니다: {case_folder}"]
    
    # 원본 폴더가 존재하는지 확인
    if not os.path.exists(original_folder):
        logging.error(f"원본 폴더가 존재하지 않습니다: {original_folder}")
        return 0, [], [f"원본 폴더가 존재하지 않습니다: {original_folder}"]
    
    # 변경된 파일 수와 오류 목록
    renamed_count = 0
    renamed_files = []  # 변경된 파일 목록 추가
    errors = []
    
    # 원본 폴더 내 모든 파일 목록 가져오기
    files = [f for f in os.listdir(original_folder) if not os.path.isdir(os.path.join(original_folder, f))]
    total_files = len(files)
    
    if RICH_AVAILABLE:
        # Rich 진행 표시줄 설정
        with Progress(
            SpinnerColumn(),
            TextColumn("[phase]1차 파일명 변경 중...[/]"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[info]{task.completed}/{task.total}[/]"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[phase]파일 처리 중...[/]", total=total_files)
            
            # 원본 폴더 내 모든 파일 처리
            for filename in files:
                # 원본 파일 경로
                original_path = os.path.join(original_folder, filename)
                
                try:
                    # 파일 이름 분석
                    result = parse_filename(filename, config)
                    
                    if result:
                        # 새 파일 이름 생성
                        new_filename = result['new_filename']
                        
                        # 파일명이 변경되지 않은 경우 건너뛰기
                        if new_filename == filename:
                            progress.update(task, advance=1)
                            continue
                        
                        # 새 파일 경로
                        new_path = os.path.join(original_folder, new_filename)
                        
                        # 이미 같은 이름의 파일이 있는지 확인
                        if os.path.exists(new_path) and original_path != new_path:
                            # 파일명에 타임스탬프 추가
                            name, ext = os.path.splitext(new_filename)
                            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                            new_filename = f"{name}_{timestamp}{ext}"
                            new_path = os.path.join(original_folder, new_filename)
                        
                        # 파일명 변경
                        os.rename(original_path, new_path)
                        renamed_count += 1
                        renamed_files.append(new_filename)  # 변경된 파일 목록에 추가
                        logging.info(f"파일명 변경: {filename} -> {new_filename}")
                    else:
                        logging.warning(f"파일명 패턴 매칭 실패: {filename}")
                except Exception as e:
                    errors.append(f"파일명 변경 실패 ({filename}): {e}")
                    logging.error(f"파일명 변경 실패 ({filename}): {e}")
                
                # 진행 상태 업데이트
                progress.update(task, advance=1)
    else:
        # 기본 출력 사용
        print(f"\n총 {total_files}개 파일 처리 중...")
        
        # 원본 폴더 내 모든 파일 처리
        for i, filename in enumerate(files, 1):
            # 진행 상황 표시
            sys.stdout.write(f"\r파일 처리 중... {i}/{total_files} ({i/total_files*100:.1f}%)")
            sys.stdout.flush()
            
            # 원본 파일 경로
            original_path = os.path.join(original_folder, filename)
            
            try:
                # 파일 이름 분석
                result = parse_filename(filename, config)
                
                if result:
                    # 새 파일 이름 생성
                    new_filename = result['new_filename']
                    
                    # 파일명이 변경되지 않은 경우 건너뛰기
                    if new_filename == filename:
                        continue
                    
                    # 새 파일 경로
                    new_path = os.path.join(original_folder, new_filename)
                    
                    # 이미 같은 이름의 파일이 있는지 확인
                    if os.path.exists(new_path):
                        # 파일명에 타임스탬프 추가
                        name, ext = os.path.splitext(new_filename)
                        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                        new_filename = f"{name}_{timestamp}{ext}"
                        new_path = os.path.join(original_folder, new_filename)
                    
                    # 파일명 변경
                    os.rename(original_path, new_path)
                    renamed_count += 1
                    renamed_files.append(new_filename)  # 변경된 파일 목록에 추가
                    logging.info(f"파일명 변경: {filename} -> {new_filename}")
                    print(f"\n파일명 변경: {filename} -> {new_filename}")
                    
                else:
                    logging.warning(f"파일명 패턴 매칭 실패: {filename}")
            except Exception as e:
                errors.append(f"파일명 변경 실패 ({filename}): {e}")
                logging.error(f"파일명 변경 실패 ({filename}): {e}")
        
        print()  # 줄바꿈
    
    # 결과 반환
    return renamed_count, renamed_files, errors

# 접두어 규칙 적용
def apply_prefix_rules(filename, prefix_patterns):
    """접두어 규칙 적용"""
    # 파일 확장자 제외한 이름만 가져오기
    name, ext = os.path.splitext(filename)
    
    # 이미 접두어가 붙은 파일인지 확인
    has_prefix = False
    for prefix in prefix_patterns.keys():
        if filename.startswith(prefix):
            has_prefix = True
            # 이미 접두어가 있는 경우 접두어를 제거한 파일명 사용
            filename = filename[len(prefix):]
            name = name[len(prefix):]
            break
    
    # 특별 처리 케이스 (우선 순위가 높은 순서대로)
    
    # 판결선고조서 특별 처리 (최우선)
    if "판결선고조서" in name:
        return f"8_제출서면_{filename}"
    
    # 판결문 특별 처리
    if "판결문" in name:
        return f"9_판결_{filename}"
    
    # 항소이유서 특별 처리
    if "항소이유서" in name:
        return f"8_제출서면_{filename}"
    
    # 사실조회 회신서 특별 처리
    if "사실조회 회신" in name or "사실조회회신" in name:
        return f"7_제출증거_{filename}"
    
    # 이미 접두어가 있었던 경우 원래 접두어를 유지
    if has_prefix:
        # 각 접두어 패턴에 대해 검사
        for prefix, patterns in prefix_patterns.items():
            # 패턴이 없는 경우 (빈 접두어) 건너뛰기
            if not patterns:
                continue
                
            # 각 패턴에 대해 검사
            for pattern in patterns:
                # 정규표현식 패턴 매칭
                if re.search(pattern, name, re.IGNORECASE):
                    return f"{prefix}{filename}"
        
        # 기본 접두어 (1_기본정보_)
        return f"1_기본정보_{filename}"
    
    # 각 접두어 패턴에 대해 검사
    for prefix, patterns in prefix_patterns.items():
        # 패턴이 없는 경우 (빈 접두어) 건너뛰기
        if not patterns:
            continue
            
        # 각 패턴에 대해 검사
        for pattern in patterns:
            # 정규표현식 패턴 매칭
            if re.search(pattern, name, re.IGNORECASE):
                return f"{prefix}{filename}"
    
    # 기본 접두어 (1_기본정보_)
    return f"1_기본정보_{filename}"

# 중복 문구 제거 함수 추가
def remove_duplicate_phrases(filename):
    """파일명에서 중복 문구 제거"""
    # 파일 확장자 분리
    name, ext = os.path.splitext(filename)
    
    # 패턴 1: "등기사항전부증명서(법인))(등기사항전부증명서(법인))" 같은 패턴
    repeat_pattern1 = r"([^()]+\([^()]+\))\)\((\1)"
    name = re.sub(repeat_pattern1, r"\1", name)
    
    # 패턴 2: "입출금거래내역조회)(입출금거래내역조회" 같은 패턴
    repeat_pattern2 = r"([^()]+)\)\((\1)"
    name = re.sub(repeat_pattern2, r"\1", name)
    
    # 패턴 3: "내역)(내역" 같은 더 일반적인 패턴
    repeat_pattern3 = r"\)\(([^()]+)"
    while re.search(repeat_pattern3, name):
        name = re.sub(repeat_pattern3, r"", name)
    
    # 언더스코어로 구분된 중복 단어 제거
    words = name.split("_")
    unique_words = []
    for word in words:
        if word not in unique_words:
            unique_words.append(word)
    name = "_".join(unique_words)
    
    return name + ext

# 파일 이름에 접두어 추가
def add_prefixes_to_files(case_folder, renamed_files, original_folder_name="원본폴더", config=None):
    """파일 이름에 접두어 추가 (2차 파일명 변경)"""
    # 원본 폴더 경로
    original_folder = os.path.join(case_folder, original_folder_name)
    
    # 사건 폴더가 존재하는지 확인
    if not os.path.exists(case_folder):
        logging.error(f"사건 폴더가 존재하지 않습니다: {case_folder}")
        return 0, [f"사건 폴더가 존재하지 않습니다: {case_folder}"]
    
    # 원본 폴더가 존재하는지 확인
    if not os.path.exists(original_folder):
        logging.error(f"원본 폴더가 존재하지 않습니다: {original_folder}")
        return 0, [f"원본 폴더가 존재하지 않습니다: {original_folder}"]
    
    # 설정 파일에서 접두어 패턴 가져오기
    prefix_patterns = {}
    if config and 'file_naming_rules' in config and 'prefix_patterns' in config['file_naming_rules']:
        prefix_patterns = config['file_naming_rules']['prefix_patterns']
    
    if not prefix_patterns:
        logging.warning("접두어 패턴이 설정되지 않았습니다. 2차 파일명 변경을 건너뜁니다.")
        return 0, ["접두어 패턴이 설정되지 않았습니다."]
    
    # 변경된 파일 수와 오류 목록
    renamed_count = 0
    errors = []
    
    # 처리할 파일 목록 필터링 (이미 접두어가 있는 파일 제외)
    files_to_process = []
    for f in renamed_files:
        # 파일이 존재하는지 확인
        if os.path.exists(os.path.join(original_folder, f)):
            # 접두어가 없는 파일 또는 항소이유서, 판결문, 판결선고조서가 포함된 파일은 처리
            name, ext = os.path.splitext(f)
            if not re.match(r"^\d+_[^_]+_", f) or "항소이유서" in f or "판결문" in f or "판결선고조서" in f:
                files_to_process.append(f)
    
    total_files = len(files_to_process)
    
    if total_files == 0:
        if RICH_AVAILABLE:
            console.print("[info]2차 파일명 변경 대상 파일이 없습니다.[/]")
        else:
            print("\n2차 파일명 변경 대상 파일이 없습니다.")
        return 0, []
    
    if RICH_AVAILABLE:
        # Rich 진행 표시줄 설정
        with Progress(
            SpinnerColumn(),
            TextColumn("[phase]2차 파일명 변경 중...[/]"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[info]{task.completed}/{task.total}[/]"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[phase]접두어 추가 중...[/]", total=total_files)
            
            # 1차 파일명 변경된 파일만 처리
            for filename in files_to_process:
                # 파일이 존재하는지 확인
                file_path = os.path.join(original_folder, filename)
                if not os.path.exists(file_path):
                    logging.warning(f"파일을 찾을 수 없습니다: {filename}")
                    progress.update(task, advance=1)
                    continue
                
                try:
                    # 접두어 규칙 적용
                    new_filename = apply_prefix_rules(filename, prefix_patterns)
                    
                    # 중복 문구 제거 (2차 변경 후에도 중복 문구가 있을 수 있음)
                    new_filename = remove_duplicate_phrases(new_filename)
                    
                    # 이미 접두어가 있는 파일인 경우 기존 접두어 제거
                    if re.match(r"^\d+_[^_]+_", filename) and (new_filename != filename):
                        # 새 파일명에서 접두어 추출
                        new_prefix = re.match(r"^(\d+_[^_]+_)", new_filename).group(1)
                        # 원래 파일명에서 접두어 제거한 부분 추출
                        original_without_prefix = re.sub(r"^\d+_[^_]+_", "", filename)
                        # 새 접두어 + 원래 파일명(접두어 제외)
                        new_filename = f"{new_prefix}{original_without_prefix}"
                    
                    # 새 파일 경로
                    new_path = os.path.join(original_folder, new_filename)
                    
                    # 이미 같은 이름의 파일이 있는지 확인
                    if os.path.exists(new_path):
                        # 파일명에 타임스탬프 추가
                        name, ext = os.path.splitext(new_filename)
                        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                        new_filename = f"{name}_{timestamp}{ext}"
                        new_path = os.path.join(original_folder, new_filename)
                    
                    # 파일명 변경
                    os.rename(file_path, new_path)
                    renamed_count += 1
                    logging.info(f"2차 파일명 변경: {filename} -> {new_filename}")
                    console.print(f"[success]2차 파일명 변경: {filename} -> {new_filename}[/]")
                    
                except Exception as e:
                    errors.append(f"2차 파일명 변경 실패 ({filename}): {e}")
                    logging.error(f"2차 파일명 변경 실패 ({filename}): {e}")
                    console.print(f"[error]2차 파일명 변경 실패 ({filename}): {e}[/]")
                
                progress.update(task, advance=1)
    else:
        print(f"\n총 {total_files}개 파일 처리 중...")
        
        # 1차 파일명 변경된 파일만 처리
        for i, filename in enumerate(files_to_process, 1):
            # 진행 상황 표시
            sys.stdout.write(f"\r접두어 추가 중... {i}/{total_files} ({i/total_files*100:.1f}%)")
            sys.stdout.flush()
            
            # 파일이 존재하는지 확인
            file_path = os.path.join(original_folder, filename)
            if not os.path.exists(file_path):
                logging.warning(f"파일을 찾을 수 없습니다: {filename}")
                continue
            
            try:
                # 접두어 규칙 적용
                new_filename = apply_prefix_rules(filename, prefix_patterns)
                
                # 중복 문구 제거 (2차 변경 후에도 중복 문구가 있을 수 있음)
                new_filename = remove_duplicate_phrases(new_filename)
                
                # 이미 접두어가 있는 파일인 경우 기존 접두어 제거
                if re.match(r"^\d+_[^_]+_", filename) and (new_filename != filename):
                    # 새 파일명에서 접두어 추출
                    new_prefix = re.match(r"^(\d+_[^_]+_)", new_filename).group(1)
                    # 원래 파일명에서 접두어 제거한 부분 추출
                    original_without_prefix = re.sub(r"^\d+_[^_]+_", "", filename)
                    # 새 접두어 + 원래 파일명(접두어 제외)
                    new_filename = f"{new_prefix}{original_without_prefix}"
                
                # 새 파일 경로
                new_path = os.path.join(original_folder, new_filename)
                
                # 이미 같은 이름의 파일이 있는지 확인
                if os.path.exists(new_path):
                    # 파일명에 타임스탬프 추가
                    name, ext = os.path.splitext(new_filename)
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    new_filename = f"{name}_{timestamp}{ext}"
                    new_path = os.path.join(original_folder, new_filename)
                
                # 파일명 변경
                os.rename(file_path, new_path)
                renamed_count += 1
                logging.info(f"2차 파일명 변경: {filename} -> {new_filename}")
                print(f"\n2차 파일명 변경: {filename} -> {new_filename}")
                
            except Exception as e:
                errors.append(f"2차 파일명 변경 실패 ({filename}): {e}")
                logging.error(f"2차 파일명 변경 실패 ({filename}): {e}")
        
        print()  # 줄바꿈
    
    # 결과 반환
    return renamed_count, errors

# 변경되지 않은 파일을 "절차관련" 폴더로 이동
def move_unchanged_files(case_folder, renamed_files, original_folder_name="원본폴더", config=None):
    """변경되지 않은 파일을 지정된 폴더로 이동"""
    # 원본 폴더 경로
    original_folder = os.path.join(case_folder, original_folder_name)
    
    # 사건 폴더가 존재하는지 확인
    if not os.path.exists(case_folder):
        logging.error(f"사건 폴더가 존재하지 않습니다: {case_folder}")
        return 0, [f"사건 폴더가 존재하지 않습니다: {case_folder}"]
    
    # 원본 폴더가 존재하는지 확인
    if not os.path.exists(original_folder):
        logging.error(f"원본 폴더가 존재하지 않습니다: {original_folder}")
        return 0, [f"원본 폴더가 존재하지 않습니다: {original_folder}"]
    
    # 대상 폴더명 설정 파일에서 가져오기
    target_folder_name = "절차관련"
    if config and 'file_management' in config and 'target_folder_name' in config['file_management']:
        target_folder_name = config['file_management']['target_folder_name']
    
    # 대상 폴더 경로
    target_folder = os.path.join(case_folder, target_folder_name)
    
    # 대상 폴더가 없으면 생성
    if not os.path.exists(target_folder):
        try:
            os.makedirs(target_folder)
            logging.info(f"'{target_folder_name}' 폴더를 생성했습니다.")
        except Exception as e:
            logging.error(f"'{target_folder_name}' 폴더 생성 실패: {e}")
            return 0, [f"'{target_folder_name}' 폴더 생성 실패: {e}"]
    
    # 원본 폴더 내 모든 파일 목록 가져오기
    all_files = [f for f in os.listdir(original_folder) if not os.path.isdir(os.path.join(original_folder, f))]
    
    # 변경된 파일 목록 (파일명만 추출)
    renamed_filenames = [os.path.basename(f) for f in renamed_files]
    
    # 변경되지 않은 파일 목록 (접두어가 이미 있는 파일 제외)
    unchanged_files = [f for f in all_files if f not in renamed_filenames and not re.match(r"^\d+_[^_]+_", f)]
    
    # 이동된 파일 수와 오류 목록
    moved_count = 0
    errors = []
    
    if not unchanged_files:
        if RICH_AVAILABLE:
            console.print("[info]이동할 변경되지 않은 파일이 없습니다.[/]")
        else:
            print("\n이동할 변경되지 않은 파일이 없습니다.")
        return 0, []
    
    total_files = len(unchanged_files)
    
    if RICH_AVAILABLE:
        # Rich 진행 표시줄 설정
        with Progress(
            SpinnerColumn(),
            TextColumn("[phase]변경되지 않은 파일 이동 중...[/]"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[info]{task.completed}/{task.total}[/]"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("[phase]파일 이동 중...[/]", total=total_files)
            
            # 변경되지 않은 파일 이동
            for filename in unchanged_files:
                # 원본 파일 경로
                original_path = os.path.join(original_folder, filename)
                
                try:
                    # 대상 파일 경로
                    target_path = os.path.join(target_folder, filename)
                    
                    # 이미 같은 이름의 파일이 있는지 확인
                    if os.path.exists(target_path):
                        # 파일명에 타임스탬프 추가
                        name, ext = os.path.splitext(filename)
                        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                        new_filename = f"{name}_{timestamp}{ext}"
                        target_path = os.path.join(target_folder, new_filename)
                    
                    # 파일 이동
                    import shutil
                    shutil.move(original_path, target_path)
                    moved_count += 1
                    logging.info(f"파일 이동: {filename} -> {target_folder_name}/{os.path.basename(target_path)}")
                    console.print(f"[success]파일 이동: {filename} -> {target_folder_name}/{os.path.basename(target_path)}[/]")
                    
                except Exception as e:
                    errors.append(f"파일 이동 실패 ({filename}): {e}")
                    logging.error(f"파일 이동 실패 ({filename}): {e}")
                    console.print(f"[error]파일 이동 실패 ({filename}): {e}[/]")
                
                progress.update(task, advance=1)
    else:
        print(f"\n총 {total_files}개 파일 이동 중...")
        
        # 변경되지 않은 파일 이동
        for i, filename in enumerate(unchanged_files, 1):
            # 진행 상황 표시
            sys.stdout.write(f"\r파일 이동 중... {i}/{total_files} ({i/total_files*100:.1f}%)")
            sys.stdout.flush()
            
            # 원본 파일 경로
            original_path = os.path.join(original_folder, filename)
            
            try:
                # 대상 파일 경로
                target_path = os.path.join(target_folder, filename)
                
                # 이미 같은 이름의 파일이 있는지 확인
                if os.path.exists(target_path):
                    # 파일명에 타임스탬프 추가
                    name, ext = os.path.splitext(filename)
                    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                    new_filename = f"{name}_{timestamp}{ext}"
                    target_path = os.path.join(target_folder, new_filename)
                
                # 파일 이동
                import shutil
                shutil.move(original_path, target_path)
                moved_count += 1
                logging.info(f"파일 이동: {filename} -> {target_folder_name}/{os.path.basename(target_path)}")
                print(f"\n파일 이동: {filename} -> {target_folder_name}/{os.path.basename(target_path)}")
                
            except Exception as e:
                errors.append(f"파일 이동 실패 ({filename}): {e}")
                logging.error(f"파일 이동 실패 ({filename}): {e}")
        
        print()  # 줄바꿈
    
    # 결과 반환
    return moved_count, errors

# 메인 함수
def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='전자소송 파일 이름 변경')
    parser.add_argument('case_folder', nargs='?', help='사건 폴더 경로')
    parser.add_argument('--original-folder', '-o', help='원본 폴더명')
    parser.add_argument('--config', help='설정 파일 경로')
    parser.add_argument('--skip-second-phase', action='store_true', help='2차 파일명 변경 건너뛰기')
    parser.add_argument('--skip-move-unchanged', action='store_true', help='변경되지 않은 파일 이동 건너뛰기')
    parser.add_argument('--target-folder', help='변경되지 않은 파일을 이동할 대상 폴더명', default='절차관련')
    
    args = parser.parse_args()
    
    # 설정 파일 경로
    config_path = args.config or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.yaml')
    
    # 설정 파일 로드
    config = None
    if os.path.exists(config_path):
        try:
            config = load_config(config_path)
            if RICH_AVAILABLE:
                console.print(f"[info]설정 파일을 로드했습니다: {config_path}[/]")
            else:
                print(f"설정 파일을 로드했습니다: {config_path}")
        except Exception as e:
            if RICH_AVAILABLE:
                console.print(f"[error]설정 파일 로드 실패: {e}[/]")
            else:
                print(f"설정 파일 로드 실패: {e}")
            return 1
    else:
        if RICH_AVAILABLE:
            console.print(f"[warning]설정 파일을 찾을 수 없습니다: {config_path}. 기본값을 사용합니다.[/]")
        else:
            print(f"설정 파일을 찾을 수 없습니다: {config_path}. 기본값을 사용합니다.")
    
    # 로깅 설정
    log_level = "INFO"
    log_file = None
    if config and 'logging' in config:
        log_level = config['logging'].get('level', "INFO")
        log_dir = config['logging'].get('log_dir', "logs")
        log_file_name = config['logging'].get('file', "file_manager.log")
        
        # 로그 디렉토리 생성
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        log_file = os.path.join(log_dir, log_file_name)
    
    setup_logging(log_level, log_file)
    
    # 설정 파일에서 값 가져오기
    original_folder_name = args.original_folder
    if not original_folder_name and config:
        original_folder_name = config.get('file_management', {}).get('original_folder_name', '원본폴더')
    
    # 사건 폴더 경로 가져오기
    case_folder = args.case_folder
    if not case_folder:
        if config and config.get('general', {}).get('case_folder'):
            case_folder = config['general']['case_folder']
        else:
            case_folder = get_case_folder()
    
    # 따옴표 제거 및 경로 정규화
    case_folder = os.path.normpath(case_folder.strip('"\'') if isinstance(case_folder, str) else case_folder)
    
    # 1차 파일 이름 변경 실행
    try:
        if RICH_AVAILABLE:
            console.print(Panel("[phase]1차 파일명 변경 시작[/]", title="파일 이름 변경 작업", border_style="blue"))
        else:
            print("\n1차 파일명 변경 시작...")
        
        renamed_count, renamed_files, errors = rename_files(case_folder, original_folder_name, config)
        
        # 결과 출력
        if RICH_AVAILABLE:
            # 결과 테이블 생성
            table = Table(title="1차 파일명 변경 결과", border_style="cyan")
            table.add_column("항목", style="cyan")
            table.add_column("값", style="green")
            table.add_row("변경된 파일 수", str(renamed_count))
            table.add_row("처리된 총 파일 수", str(len(os.listdir(os.path.join(case_folder, original_folder_name)))))
            
            # 변경된 파일 목록 추가
            if renamed_count > 0:
                renamed_files_table = Table(title="변경된 파일 목록", box=None)
                renamed_files_table.add_column("원본 파일명", style="filename")
                renamed_files_table.add_column("→", style="cyan")
                renamed_files_table.add_column("변경된 파일명", style="newname")
                
                # 최대 10개까지만 표시
                max_display = min(10, len(renamed_files))
                for i in range(max_display):
                    renamed_files_table.add_row("원본파일", "→", renamed_files[i])
                
                if len(renamed_files) > max_display:
                    renamed_files_table.add_row(f"외 {len(renamed_files) - max_display}개 파일", "", "")
                
                table.add_row("변경된 파일 목록", "")
                table.add_row(renamed_files_table, "")
            
            console.print(table)
            
            # 오류가 있는 경우 패널로 표시
            if errors:
                error_panel = Panel("\n".join([f"- {error}" for error in errors]), 
                                    title="[error]1차 파일명 변경 오류[/]", 
                                    border_style="red")
                console.print(error_panel)
                return 1
        else:
            print(f"\n1차 파일명 변경 완료:")
            print(f"- 변경된 파일 수: {renamed_count}")
            
            if errors:
                print("\n1차 파일명 변경 오류 목록:")
                for error in errors:
                    print(f"- {error}")
                return 1
        
        # 2차 파일 이름 변경 실행 (접두어 추가)
        if not args.skip_second_phase and renamed_files:
            if RICH_AVAILABLE:
                console.print(Panel("[phase]2차 파일명 변경 시작 (접두어 추가)[/]", title="파일 이름 변경 작업", border_style="blue"))
            else:
                print("\n2차 파일명 변경 시작 (접두어 추가)...")
            
            prefix_renamed_count, prefix_errors = add_prefixes_to_files(case_folder, renamed_files, original_folder_name, config)
            
            # 결과 출력
            if RICH_AVAILABLE:
                # 결과 테이블 생성
                table = Table(title="2차 파일명 변경 결과", border_style="cyan")
                table.add_column("항목", style="cyan")
                table.add_column("값", style="green")
                table.add_row("변경된 파일 수", str(prefix_renamed_count))
                table.add_row("대상 파일 수", str(len(renamed_files)))
                console.print(table)
                
                # 오류가 있는 경우 패널로 표시
                if prefix_errors:
                    error_panel = Panel("\n".join([f"- {error}" for error in prefix_errors]), 
                                        title="[error]2차 파일명 변경 오류[/]", 
                                        border_style="red")
                    console.print(error_panel)
                    return 1
                
                # 성공 메시지
                if prefix_renamed_count > 0:
                    console.print(Panel("[success]파일 이름 변경 작업이 성공적으로 완료되었습니다![/]", 
                                       border_style="green"))
                else:
                    console.print("[info]2차 파일명 변경 대상 파일이 없었습니다.[/]")
            else:
                print(f"\n2차 파일명 변경 완료:")
                print(f"- 변경된 파일 수: {prefix_renamed_count}")
                
                if prefix_errors:
                    print("\n2차 파일명 변경 오류 목록:")
                    for error in prefix_errors:
                        print(f"- {error}")
                    return 1
        
        # 변경되지 않은 파일 이동
        if not args.skip_move_unchanged:
            if RICH_AVAILABLE:
                console.print(Panel("[phase]변경되지 않은 파일 이동 시작[/]", title="파일 이동 작업", border_style="blue"))
            else:
                print("\n변경되지 않은 파일 이동 시작...")
            
            moved_count, move_errors = move_unchanged_files(case_folder, renamed_files, original_folder_name, config)
            
            # 결과 출력
            if RICH_AVAILABLE:
                # 결과 테이블 생성
                table = Table(title="파일 이동 결과", border_style="cyan")
                table.add_column("항목", style="cyan")
                table.add_column("값", style="green")
                table.add_row("이동된 파일 수", str(moved_count))
                console.print(table)
                
                # 오류가 있는 경우 패널로 표시
                if move_errors:
                    error_panel = Panel("\n".join([f"- {error}" for error in move_errors]), 
                                        title="[error]파일 이동 오류[/]", 
                                        border_style="red")
                    console.print(error_panel)
                
                # 성공 메시지
                if moved_count > 0:
                    console.print(Panel(f"[success]변경되지 않은 {moved_count}개 파일이 '{args.target_folder}' 폴더로 이동되었습니다![/]", 
                                       border_style="green"))
                else:
                    console.print("[info]이동할 변경되지 않은 파일이 없었습니다.[/]")
            else:
                print(f"\n파일 이동 완료:")
                print(f"- 이동된 파일 수: {moved_count}")
                
                if move_errors:
                    print("\n파일 이동 오류 목록:")
                    for error in move_errors:
                        print(f"- {error}")
        
        return 0
    except Exception as e:
        if RICH_AVAILABLE:
            console.print(Panel(f"[error]예기치 않은 오류 발생: {e}[/]", 
                               title="오류", border_style="red"))
        else:
            logging.error(f"예기치 않은 오류 발생: {e}")
            print(f"예기치 않은 오류 발생: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())