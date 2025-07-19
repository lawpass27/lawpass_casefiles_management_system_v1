#!/usr/bin/env python3
"""
크로스 플랫폼 설정 관리 모듈
플랫폼별 설정을 자동으로 처리하고 경로를 변환하는 기능 제공
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union
from .platform_utils import get_platform_manager

logger = logging.getLogger(__name__)


class ConfigManager:
    """크로스 플랫폼 설정 관리 클래스"""
    
    def __init__(self, config_path: Union[str, Path] = None):
        """
        ConfigManager 초기화
        
        Args:
            config_path: 설정 파일 경로 (기본값: 프로젝트 루트의 config.yaml)
        """
        self.platform_manager = get_platform_manager()
        
        if config_path is None:
            # 현재 스크립트의 부모 디렉토리에서 config.yaml 찾기
            current_dir = Path(__file__).parent.parent
            config_path = current_dir / "config.yaml"
        
        self.config_path = Path(config_path)
        self._config = None
        self._load_config()
    
    def _load_config(self) -> None:
        """설정 파일 로드"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
            logger.debug(f"설정 파일 로드 완료: {self.config_path}")
        except Exception as e:
            logger.error(f"설정 파일 로드 실패: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """기본 설정 반환"""
        return {
            'general': {
                'source_folder': '',
                'case_folder': '',
                'backup_folder': ''
            },
            'text_extraction': {
                'poppler_path': '',
                'google_credentials_path': ''
            }
        }
    
    def _substitute_placeholders(self, value: str) -> str:
        """플레이스홀더 치환"""
        if not isinstance(value, str):
            return value
        
        # 기본 경로 정보 가져오기
        default_paths = self.platform_manager.get_default_config_paths()
        
        # 플레이스홀더 치환
        substitutions = {
            '{username}': os.environ.get('USERNAME', os.environ.get('USER', 'user')),
            '{user_documents}': default_paths.get('documents', ''),
            '{user_downloads}': default_paths.get('downloads', ''),
            '{config_dir}': default_paths.get('config_dir', ''),
            '{temp_dir}': default_paths.get('temp', '')
        }
        
        result = value
        for placeholder, replacement in substitutions.items():
            if placeholder in result:
                result = result.replace(placeholder, replacement)
        
        return result
    
    def _get_platform_specific_value(self, base_value: Any, platform_key: str, specific_key: str) -> Any:
        """플랫폼별 특정 값 가져오기"""
        platform_id = self.platform_manager.info.platform_id
        
        # 플랫폼별 설정 확인
        if (platform_key in self._config and 
            isinstance(self._config[platform_key], dict) and
            platform_id in self._config[platform_key] and
            specific_key in self._config[platform_key][platform_id]):
            
            platform_value = self._config[platform_key][platform_id][specific_key]
            
            # 플레이스홀더 치환
            if isinstance(platform_value, str):
                platform_value = self._substitute_placeholders(platform_value)
            
            # 경로 변환
            if isinstance(platform_value, str) and platform_value:
                platform_value = self.platform_manager.path.convert_windows_path(platform_value)
            
            return platform_value
        
        # 기본값 사용
        if isinstance(base_value, str):
            # 플레이스홀더 치환
            base_value = self._substitute_placeholders(base_value)
            # 경로 변환
            if base_value:
                base_value = self.platform_manager.path.convert_windows_path(base_value)
        
        return base_value
    
    def get_path(self, config_section: str, key: str, default: str = '') -> str:
        """
        플랫폼에 맞는 경로 반환
        
        Args:
            config_section: 설정 섹션명
            key: 설정 키
            default: 기본값
        
        Returns:
            변환된 경로
        """
        try:
            section = self._config.get(config_section, {})
            base_value = section.get(key, default)
            
            # 플랫폼별 설정 확인
            if config_section == 'general':
                platform_value = self._get_platform_specific_value(
                    base_value, 'general.platform_specific', key
                )
            elif config_section == 'text_extraction':
                platform_value = self._get_platform_specific_value(
                    base_value, 'text_extraction.platform_tools', key
                )
            else:
                # 기본값 처리
                if isinstance(base_value, str):
                    base_value = self._substitute_placeholders(base_value)
                    if base_value:
                        base_value = self.platform_manager.path.convert_windows_path(base_value)
                platform_value = base_value
            
            return platform_value or default
            
        except Exception as e:
            logger.warning(f"경로 설정 가져오기 실패 ({config_section}.{key}): {e}")
            return default
    
    def get_setting(self, config_section: str, key: str, default: Any = None) -> Any:
        """
        일반 설정 값 반환
        
        Args:
            config_section: 설정 섹션명
            key: 설정 키
            default: 기본값
        
        Returns:
            설정 값
        """
        try:
            section = self._config.get(config_section, {})
            return section.get(key, default)
        except Exception as e:
            logger.warning(f"설정 가져오기 실패 ({config_section}.{key}): {e}")
            return default
    
    def get_section(self, section_name: str) -> Dict[str, Any]:
        """
        전체 설정 섹션 반환
        
        Args:
            section_name: 섹션명
        
        Returns:
            설정 섹션 딕셔너리
        """
        return self._config.get(section_name, {})
    
    def update_setting(self, config_section: str, key: str, value: Any) -> None:
        """
        설정 값 업데이트
        
        Args:
            config_section: 설정 섹션명
            key: 설정 키
            value: 새 값
        """
        if config_section not in self._config:
            self._config[config_section] = {}
        
        self._config[config_section][key] = value
    
    def save_config(self) -> bool:
        """설정 파일 저장"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            logger.info(f"설정 파일 저장 완료: {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"설정 파일 저장 실패: {e}")
            return False
    
    def get_all_paths(self) -> Dict[str, str]:
        """모든 경로 설정을 플랫폼에 맞게 변환하여 반환"""
        paths = {}
        
        # general 섹션 경로들
        general_paths = ['source_folder', 'case_folder', 'backup_folder']
        for path_key in general_paths:
            paths[path_key] = self.get_path('general', path_key)
        
        # text_extraction 섹션 경로들
        extraction_paths = ['poppler_path', 'google_credentials_path']
        for path_key in extraction_paths:
            paths[path_key] = self.get_path('text_extraction', path_key)
        
        return paths
    
    def validate_paths(self) -> Dict[str, bool]:
        """경로 유효성 검사"""
        paths = self.get_all_paths()
        results = {}
        
        for key, path in paths.items():
            if not path:  # 빈 경로는 유효하지 않은 것으로 처리
                results[key] = False
                continue
            
            try:
                # 경로 확장 (~ 등)
                expanded_path = os.path.expanduser(path)
                results[key] = os.path.exists(expanded_path)
            except:
                results[key] = False
        
        return results
    
    def get_environment_config(self) -> Dict[str, str]:
        """환경 변수와 설정을 통합하여 반환"""
        config = {}
        
        # Google Cloud 인증 정보
        google_creds = (
            self.platform_manager.env.get_platform_env('GOOGLE_CLOUD_CREDENTIALS') or
            self.get_path('text_extraction', 'google_credentials_path')
        )
        if google_creds:
            config['google_credentials_path'] = google_creds
        
        # Poppler 경로
        poppler_path = (
            self.platform_manager.env.get_platform_env('POPPLER_PATH') or
            self.get_path('text_extraction', 'poppler_path')
        )
        if poppler_path:
            config['poppler_path'] = poppler_path
        
        return config


# 싱글톤 인스턴스
_config_manager = None

def get_config_manager(config_path: Union[str, Path] = None) -> ConfigManager:
    """ConfigManager 싱글톤 인스턴스 반환"""
    global _config_manager
    if _config_manager is None or config_path is not None:
        _config_manager = ConfigManager(config_path)
    return _config_manager

# 편의 함수들
def get_path(section: str, key: str, default: str = '') -> str:
    """플랫폼에 맞는 경로 반환"""
    return get_config_manager().get_path(section, key, default)

def get_setting(section: str, key: str, default: Any = None) -> Any:
    """설정 값 반환"""
    return get_config_manager().get_setting(section, key, default)

def get_all_paths() -> Dict[str, str]:
    """모든 경로 설정 반환"""
    return get_config_manager().get_all_paths()

def validate_config_paths() -> Dict[str, bool]:
    """설정 경로 유효성 검사"""
    return get_config_manager().validate_paths()