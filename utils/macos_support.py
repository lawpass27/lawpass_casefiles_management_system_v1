#!/usr/bin/env python3
"""
macOS 특화 지원 모듈
macOS 환경에서의 특별한 요구사항과 기능을 처리
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Dict
from .platform_utils import get_platform_info

logger = logging.getLogger(__name__)


class MacOSHelper:
    """macOS 특화 도움 클래스"""
    
    def __init__(self):
        self.platform_info = get_platform_info()
        self.is_macos = self.platform_info.is_mac
    
    def check_homebrew_installed(self) -> bool:
        """Homebrew 설치 여부 확인"""
        if not self.is_macos:
            return False
        
        try:
            result = subprocess.run(['which', 'brew'], 
                                  capture_output=True, text=True, check=True)
            return bool(result.stdout.strip())
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def install_homebrew_package(self, package_name: str) -> bool:
        """Homebrew 패키지 설치"""
        if not self.is_macos or not self.check_homebrew_installed():
            logger.warning("Homebrew가 설치되어 있지 않습니다.")
            return False
        
        try:
            subprocess.run(['brew', 'install', package_name], check=True)
            logger.info(f"Homebrew 패키지 설치 완료: {package_name}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Homebrew 패키지 설치 실패: {package_name} - {e}")
            return False
    
    def check_dependencies(self) -> Dict[str, bool]:
        """macOS에서 필요한 의존성 확인"""
        dependencies = {
            'poppler': False,
            'tesseract': False,
            'python3': False,
            'git': False
        }
        
        if not self.is_macos:
            return dependencies
        
        # poppler 확인 (pdf2image 의존성)
        try:
            subprocess.run(['pdftoppm', '-h'], 
                          capture_output=True, check=True)
            dependencies['poppler'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # tesseract 확인
        try:
            subprocess.run(['tesseract', '--version'], 
                          capture_output=True, check=True)
            dependencies['tesseract'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # python3 확인
        try:
            subprocess.run(['python3', '--version'], 
                          capture_output=True, check=True)
            dependencies['python3'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # git 확인
        try:
            subprocess.run(['git', '--version'], 
                          capture_output=True, check=True)
            dependencies['git'] = True
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        return dependencies
    
    def setup_macos_environment(self) -> bool:
        """macOS 환경 설정"""
        if not self.is_macos:
            logger.warning("macOS가 아닙니다.")
            return False
        
        success = True
        
        # Homebrew 확인 및 설치 안내
        if not self.check_homebrew_installed():
            logger.warning("Homebrew가 설치되어 있지 않습니다.")
            logger.info("Homebrew 설치 명령어: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
            success = False
        
        # 의존성 확인
        deps = self.check_dependencies()
        missing_deps = [dep for dep, installed in deps.items() if not installed]
        
        if missing_deps:
            logger.warning(f"누락된 의존성: {', '.join(missing_deps)}")
            if self.check_homebrew_installed():
                logger.info("Homebrew로 설치 가능한 패키지:")
                for dep in missing_deps:
                    if dep in ['poppler', 'tesseract']:
                        logger.info(f"  brew install {dep}")
            success = False
        
        return success
    
    def get_default_directories(self) -> Dict[str, str]:
        """macOS 기본 디렉토리 반환"""
        home = Path.home()
        
        return {
            'desktop': str(home / 'Desktop'),
            'documents': str(home / 'Documents'),
            'downloads': str(home / 'Downloads'),
            'pictures': str(home / 'Pictures'),
            'movies': str(home / 'Movies'),
            'music': str(home / 'Music'),
            'applications': '/Applications',
            'library': str(home / 'Library'),
            'temp': '/tmp'
        }
    
    def open_finder(self, path: str) -> bool:
        """Finder에서 경로 열기"""
        if not self.is_macos:
            return False
        
        try:
            subprocess.run(['open', '-R', path], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Finder 열기 실패: {e}")
            return False
    
    def show_notification(self, title: str, message: str, subtitle: str = '') -> bool:
        """macOS 알림 표시"""
        if not self.is_macos:
            return False
        
        try:
            cmd = ['osascript', '-e', f'display notification "{message}" with title "{title}"']
            if subtitle:
                cmd[-1] += f' subtitle "{subtitle}"'
            
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"알림 표시 실패: {e}")
            return False
    
    def request_accessibility_permission(self) -> bool:
        """접근성 권한 요청"""
        if not self.is_macos:
            return False
        
        try:
            # 시스템 환경설정의 보안 및 개인정보 보호 페이지 열기
            subprocess.run([
                'open', 
                'x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility'
            ], check=True)
            
            logger.info("시스템 환경설정에서 접근성 권한을 허용해주세요.")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"접근성 권한 요청 실패: {e}")
            return False
    
    def get_system_info(self) -> Dict[str, str]:
        """macOS 시스템 정보 반환"""
        if not self.is_macos:
            return {}
        
        info = {}
        
        try:
            # macOS 버전
            result = subprocess.run(['sw_vers', '-productVersion'], 
                                  capture_output=True, text=True, check=True)
            info['macos_version'] = result.stdout.strip()
        except:
            info['macos_version'] = 'Unknown'
        
        try:
            # CPU 아키텍처
            result = subprocess.run(['uname', '-m'], 
                                  capture_output=True, text=True, check=True)
            info['architecture'] = result.stdout.strip()
        except:
            info['architecture'] = 'Unknown'
        
        try:
            # 메모리 정보
            result = subprocess.run(['sysctl', '-n', 'hw.memsize'], 
                                  capture_output=True, text=True, check=True)
            memory_bytes = int(result.stdout.strip())
            memory_gb = round(memory_bytes / (1024**3), 1)
            info['memory_gb'] = str(memory_gb)
        except:
            info['memory_gb'] = 'Unknown'
        
        return info
    
    def create_alias(self, source_path: str, alias_path: str) -> bool:
        """macOS Alias 생성"""
        if not self.is_macos:
            return False
        
        try:
            script = f'''
            tell application "Finder"
                set sourceItem to POSIX file "{source_path}" as alias
                set aliasPath to POSIX file "{alias_path}"
                make alias file to sourceItem at (container of aliasPath)
                set name of result to "{Path(alias_path).name}"
            end tell
            '''
            
            subprocess.run(['osascript', '-e', script], check=True)
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Alias 생성 실패: {e}")
            return False
    
    def get_volume_info(self) -> List[Dict[str, str]]:
        """마운트된 볼륨 정보 반환"""
        if not self.is_macos:
            return []
        
        volumes = []
        volumes_path = Path('/Volumes')
        
        if volumes_path.exists():
            for item in volumes_path.iterdir():
                if item.is_dir():
                    try:
                        stat = item.stat()
                        volumes.append({
                            'name': item.name,
                            'path': str(item),
                            'free_space': self._get_free_space(str(item))
                        })
                    except:
                        pass
        
        return volumes
    
    def _get_free_space(self, path: str) -> str:
        """경로의 여유 공간 반환"""
        try:
            result = subprocess.run(['df', '-h', path], 
                                  capture_output=True, text=True, check=True)
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) >= 4:
                    return parts[3]  # Available 컬럼
        except:
            pass
        return 'Unknown'


def get_macos_helper() -> MacOSHelper:
    """MacOSHelper 인스턴스 반환"""
    return MacOSHelper()

def setup_macos_environment() -> bool:
    """macOS 환경 설정 (편의 함수)"""
    return get_macos_helper().setup_macos_environment()

def check_macos_dependencies() -> Dict[str, bool]:
    """macOS 의존성 확인 (편의 함수)"""
    return get_macos_helper().check_dependencies()

def show_macos_notification(title: str, message: str, subtitle: str = '') -> bool:
    """macOS 알림 표시 (편의 함수)"""
    return get_macos_helper().show_notification(title, message, subtitle)