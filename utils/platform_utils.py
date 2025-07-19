#!/usr/bin/env python3
"""
통합 플랫폼 유틸리티 모듈
Windows, WSL, macOS 환경에서의 크로스 플랫폼 호환성을 위한 통합 유틸리티
"""

import os
import re
import platform
import subprocess
from pathlib import Path
from typing import Dict, Optional, Union, Tuple
import logging

logger = logging.getLogger(__name__)


class PlatformInfo:
    """플랫폼 정보를 담는 데이터 클래스"""
    
    def __init__(self):
        self._detect_platform()
    
    def _detect_platform(self):
        """플랫폼을 감지하고 정보를 설정"""
        self.system = platform.system()
        self.is_windows = self.system == "Windows"
        self.is_mac = self.system == "Darwin"
        self.is_linux = self.system == "Linux"
        self.is_wsl = self._detect_wsl()
        
        # 플랫폼 식별자
        if self.is_wsl:
            self.platform_id = "wsl"
        elif self.is_windows:
            self.platform_id = "windows"
        elif self.is_mac:
            self.platform_id = "macos"
        elif self.is_linux:
            self.platform_id = "linux"
        else:
            self.platform_id = "unknown"
    
    def _detect_wsl(self) -> bool:
        """WSL 환경 감지"""
        if not self.is_linux:
            return False
        
        try:
            # /proc/version 파일에서 WSL 감지
            with open('/proc/version', 'r') as f:
                version_info = f.read().lower()
                return 'microsoft' in version_info or 'wsl' in version_info
        except (FileNotFoundError, PermissionError):
            # uname으로 대체 감지 시도
            try:
                uname_release = platform.uname().release.lower()
                return 'microsoft' in uname_release or 'wsl' in uname_release
            except:
                return False
    
    def to_dict(self) -> Dict[str, Union[str, bool]]:
        """플랫폼 정보를 딕셔너리로 반환"""
        return {
            'system': self.system,
            'platform_id': self.platform_id,
            'is_windows': self.is_windows,
            'is_mac': self.is_mac,
            'is_linux': self.is_linux,
            'is_wsl': self.is_wsl
        }


class PathManager:
    """크로스 플랫폼 경로 관리 클래스"""
    
    def __init__(self, platform_info: PlatformInfo):
        self.platform = platform_info
    
    def convert_windows_path(self, windows_path: str) -> str:
        """
        Windows 경로를 현재 플랫폼에 맞는 경로로 변환
        
        Args:
            windows_path: Windows 형식의 경로 (예: "D:\\folder\\file.txt")
        
        Returns:
            변환된 경로
        """
        if not windows_path:
            return windows_path
        
        # Windows에서는 그대로 반환
        if self.platform.is_windows:
            return str(Path(windows_path))
        
        # WSL 환경에서의 변환
        if self.platform.is_wsl:
            return self._convert_to_wsl_path(windows_path)
        
        # macOS/Linux에서의 변환 (홈 디렉토리 기반)
        return self._convert_to_unix_path(windows_path)
    
    def _convert_to_wsl_path(self, windows_path: str) -> str:
        """Windows 경로를 WSL 경로로 변환"""
        # 드라이브 문자 패턴 매칭 (예: C:\, D:\\, C:/)
        match = re.match(r'^([A-Za-z]):[\\/]+(.*)$', windows_path)
        
        if match:
            drive_letter = match.group(1).lower()
            rest_path = match.group(2)
            
            # 백슬래시를 슬래시로 변환하고 정규화
            rest_path = rest_path.replace('\\', '/')
            rest_path = re.sub(r'/+', '/', rest_path)  # 연속 슬래시 제거
            rest_path = rest_path.rstrip('/')  # 끝의 슬래시 제거
            
            wsl_path = f"/mnt/{drive_letter}"
            if rest_path:
                wsl_path += f"/{rest_path}"
            
            logger.debug(f"WSL path conversion: '{windows_path}' -> '{wsl_path}'")
            return wsl_path
        
        # 드라이브 문자가 없는 경우 슬래시만 변환
        return windows_path.replace('\\', '/')
    
    def _convert_to_unix_path(self, windows_path: str) -> str:
        """Windows 경로를 Unix 계열 경로로 변환 (macOS/Linux)"""
        # 기본적으로 홈 디렉토리 기반으로 변환
        home = Path.home()
        
        # 드라이브 문자 제거하고 상대 경로로 변환
        match = re.match(r'^([A-Za-z]):[\\/]+(.*)$', windows_path)
        if match:
            rest_path = match.group(2).replace('\\', '/')
            # Documents 폴더 기반으로 변환
            unix_path = home / "Documents" / rest_path
            return str(unix_path)
        
        return windows_path.replace('\\', '/')
    
    def normalize_path(self, path: Union[str, Path]) -> str:
        """경로를 정규화"""
        return str(Path(path).resolve())
    
    def ensure_directory(self, path: Union[str, Path]) -> bool:
        """디렉토리가 존재하지 않으면 생성"""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except (PermissionError, OSError) as e:
            logger.error(f"디렉토리 생성 실패: {path} - {e}")
            return False
    
    def validate_path(self, path: Union[str, Path]) -> bool:
        """경로의 유효성 검사"""
        try:
            return Path(path).exists()
        except (OSError, ValueError):
            return False


class EnvironmentManager:
    """환경 변수 관리 클래스"""
    
    def __init__(self, platform_info: PlatformInfo):
        self.platform = platform_info
    
    def get_platform_env(self, base_var_name: str, default: str = '') -> str:
        """
        플랫폼별 환경 변수를 가져옴
        
        Args:
            base_var_name: 기본 환경 변수 이름
            default: 기본값
        
        Returns:
            환경 변수 값
        """
        # 먼저 기본 환경 변수 확인
        value = os.environ.get(base_var_name, '')
        if value:
            return value
        
        # 플랫폼별 환경 변수 확인
        platform_var = f"{base_var_name}_{self.platform.platform_id.upper()}"
        return os.environ.get(platform_var, default)
    
    def set_platform_env(self, base_var_name: str, value: str) -> None:
        """플랫폼별 환경 변수 설정"""
        os.environ[base_var_name] = value


class CommandExecutor:
    """플랫폼별 명령 실행 클래스"""
    
    def __init__(self, platform_info: PlatformInfo):
        self.platform = platform_info
    
    def open_url(self, url: str) -> bool:
        """플랫폼에 맞는 방식으로 URL 열기"""
        try:
            if self.platform.is_wsl:
                subprocess.run(['wslview', url], check=True)
            elif self.platform.is_windows:
                subprocess.run(['start', url], shell=True, check=True)
            elif self.platform.is_mac:
                subprocess.run(['open', url], check=True)
            else:  # Linux
                subprocess.run(['xdg-open', url], check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.error(f"URL 열기 실패: {url} - {e}")
            return False
    
    def copy_to_clipboard(self, text: str) -> bool:
        """플랫폼에 맞는 방식으로 클립보드에 복사"""
        try:
            if self.platform.is_wsl:
                # WSL에서는 Windows 클립보드 사용
                subprocess.run(['clip.exe'], input=text.encode('utf-8'), check=True)
            elif self.platform.is_windows:
                subprocess.run(['clip'], input=text.encode('utf-8'), check=True)
            elif self.platform.is_mac:
                subprocess.run(['pbcopy'], input=text.encode('utf-8'), check=True)
            else:  # Linux
                # xclip 시도
                try:
                    subprocess.run(['xclip', '-selection', 'clipboard'], 
                                 input=text.encode('utf-8'), check=True)
                except FileNotFoundError:
                    # xsel 시도
                    subprocess.run(['xsel', '--clipboard', '--input'], 
                                 input=text.encode('utf-8'), check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            logger.warning(f"클립보드 복사 실패: {e}")
            return False
    
    def get_npm_command(self) -> str:
        """플랫폼에 맞는 npm 명령어 반환"""
        if self.platform.is_windows:
            return "npm.cmd"
        else:
            return "npm"


class PlatformManager:
    """통합 플랫폼 관리 클래스"""
    
    def __init__(self):
        self.info = PlatformInfo()
        self.path = PathManager(self.info)
        self.env = EnvironmentManager(self.info)
        self.cmd = CommandExecutor(self.info)
    
    def get_default_config_paths(self) -> Dict[str, str]:
        """플랫폼별 기본 설정 경로 반환"""
        home = Path.home()
        
        if self.info.is_windows:
            return {
                'config_dir': str(home / '.config'),
                'documents': str(home / 'Documents'),
                'downloads': str(home / 'Downloads'),
                'temp': os.environ.get('TEMP', str(home / 'AppData' / 'Local' / 'Temp'))
            }
        elif self.info.is_wsl:
            # WSL에서는 Windows 사용자 디렉토리 활용
            windows_user = os.environ.get('USERNAME', 'user')
            return {
                'config_dir': f'/mnt/c/Users/{windows_user}/.config',
                'documents': f'/mnt/c/Users/{windows_user}/Documents',
                'downloads': f'/mnt/c/Users/{windows_user}/Downloads',
                'temp': '/tmp'
            }
        elif self.info.is_mac:
            return {
                'config_dir': str(home / '.config'),
                'documents': str(home / 'Documents'),
                'downloads': str(home / 'Downloads'),
                'temp': '/tmp'
            }
        else:  # Linux
            return {
                'config_dir': str(home / '.config'),
                'documents': str(home / 'Documents'),
                'downloads': str(home / 'Downloads'),
                'temp': '/tmp'
            }
    
    def should_use_parallel_processing(self) -> bool:
        """플랫폼에서 병렬 처리 사용 가능 여부"""
        # Windows에서는 플랫폼 감지 이슈로 인해 비활성화
        return not self.info.is_windows


# 싱글톤 인스턴스
_platform_manager = None

def get_platform_manager() -> PlatformManager:
    """플랫폼 매니저 싱글톤 인스턴스 반환"""
    global _platform_manager
    if _platform_manager is None:
        _platform_manager = PlatformManager()
    return _platform_manager


# 편의 함수들
def get_platform_info() -> PlatformInfo:
    """현재 플랫폼 정보 반환"""
    return get_platform_manager().info

def convert_path(windows_path: str) -> str:
    """Windows 경로를 현재 플랫폼 경로로 변환"""
    return get_platform_manager().path.convert_windows_path(windows_path)

def get_env_var(var_name: str, default: str = '') -> str:
    """플랫폼별 환경 변수 가져오기"""
    return get_platform_manager().env.get_platform_env(var_name, default)

def copy_to_clipboard(text: str) -> bool:
    """클립보드에 텍스트 복사"""
    return get_platform_manager().cmd.copy_to_clipboard(text)

def open_url(url: str) -> bool:
    """URL 열기"""
    return get_platform_manager().cmd.open_url(url)