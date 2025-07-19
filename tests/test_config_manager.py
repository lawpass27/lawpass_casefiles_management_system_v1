#!/usr/bin/env python3
"""
설정 관리자 테스트 모듈
"""

import unittest
import tempfile
import sys
import os
import yaml
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.config_manager import ConfigManager, get_config_manager


class TestConfigManager(unittest.TestCase):
    """ConfigManager 테스트"""
    
    def setUp(self):
        """테스트 설정 파일 생성"""
        self.test_config = {
            'general': {
                'source_folder': 'D:\\test_source',
                'backup_folder': 'D:\\test_backup',
                'platform_specific': {
                    'windows': {
                        'source_folder': 'D:\\windows_source',
                        'backup_folder': 'D:\\windows_backup'
                    },
                    'wsl': {
                        'source_folder': '/mnt/d/wsl_source',
                        'backup_folder': '/mnt/d/wsl_backup'
                    },
                    'macos': {
                        'source_folder': '~/Documents/macos_source',
                        'backup_folder': '~/Documents/macos_backup'
                    }
                }
            },
            'text_extraction': {
                'poppler_path': 'C:\\test_poppler',
                'google_credentials_path': 'C:\\test_credentials.json',
                'platform_tools': {
                    'windows': {
                        'poppler_path': 'C:\\windows_poppler',
                        'google_credentials_path': 'C:\\windows_credentials.json'
                    },
                    'wsl': {
                        'poppler_path': '',
                        'google_credentials_path': '/mnt/c/Users/{username}/.config/test.json'
                    },
                    'macos': {
                        'poppler_path': '/usr/local/bin',
                        'google_credentials_path': '~/.config/test.json'
                    }
                }
            }
        }
        
        # 임시 설정 파일 생성
        self.temp_config_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(self.test_config, self.temp_config_file, allow_unicode=True)
        self.temp_config_file.close()
        
        # ConfigManager 인스턴스 생성
        self.config_manager = ConfigManager(self.temp_config_file.name)
    
    def tearDown(self):
        """정리"""
        # 임시 파일 삭제
        if os.path.exists(self.temp_config_file.name):
            os.unlink(self.temp_config_file.name)
    
    def test_config_loading(self):
        """설정 파일 로딩 테스트"""
        # 설정이 올바르게 로드되었는지 확인
        self.assertIsNotNone(self.config_manager._config)
        self.assertIn('general', self.config_manager._config)
        self.assertIn('text_extraction', self.config_manager._config)
    
    def test_get_setting(self):
        """일반 설정 가져오기 테스트"""
        # 존재하는 설정
        source_folder = self.config_manager.get_setting('general', 'source_folder')
        self.assertEqual(source_folder, 'D:\\test_source')
        
        # 존재하지 않는 설정 (기본값 반환)
        non_existent = self.config_manager.get_setting('general', 'non_existent', 'default_value')
        self.assertEqual(non_existent, 'default_value')
        
        # 존재하지 않는 섹션
        non_section = self.config_manager.get_setting('non_section', 'key', 'default')
        self.assertEqual(non_section, 'default')
    
    def test_get_path(self):
        """경로 설정 가져오기 테스트"""
        # 기본 경로 (플랫폼별 설정이 없는 경우)
        source_folder = self.config_manager.get_path('general', 'source_folder')
        self.assertIsInstance(source_folder, str)
        
        # 플랫폼별 경로는 현재 플랫폼에 따라 다르게 처리됨
        # 실제 변환은 플랫폼에 따라 달라지므로 타입만 확인
        poppler_path = self.config_manager.get_path('text_extraction', 'poppler_path')
        self.assertIsInstance(poppler_path, str)
    
    def test_placeholder_substitution(self):
        """플레이스홀더 치환 테스트"""
        # 환경 변수에서 사용자명 가져오기
        username = os.environ.get('USERNAME', os.environ.get('USER', 'testuser'))
        
        # 플레이스홀더가 포함된 값 테스트
        test_value = "C:\\Users\\{username}\\test"
        substituted = self.config_manager._substitute_placeholders(test_value)
        
        self.assertNotIn('{username}', substituted)
        self.assertIn(username, substituted)
    
    def test_get_section(self):
        """전체 섹션 가져오기 테스트"""
        general_section = self.config_manager.get_section('general')
        self.assertIsInstance(general_section, dict)
        self.assertIn('source_folder', general_section)
        
        # 존재하지 않는 섹션
        non_section = self.config_manager.get_section('non_existent')
        self.assertEqual(non_section, {})
    
    def test_update_setting(self):
        """설정 업데이트 테스트"""
        # 새 값 설정
        self.config_manager.update_setting('general', 'test_key', 'test_value')
        
        # 설정된 값 확인
        value = self.config_manager.get_setting('general', 'test_key')
        self.assertEqual(value, 'test_value')
        
        # 새 섹션 생성
        self.config_manager.update_setting('new_section', 'new_key', 'new_value')
        value = self.config_manager.get_setting('new_section', 'new_key')
        self.assertEqual(value, 'new_value')
    
    def test_get_all_paths(self):
        """모든 경로 가져오기 테스트"""
        all_paths = self.config_manager.get_all_paths()
        
        self.assertIsInstance(all_paths, dict)
        
        # 예상되는 키들이 있는지 확인
        expected_keys = [
            'source_folder', 'case_folder', 'backup_folder',
            'poppler_path', 'google_credentials_path'
        ]
        
        for key in expected_keys:
            self.assertIn(key, all_paths)
    
    def test_validate_paths(self):
        """경로 유효성 검사 테스트"""
        validation_results = self.config_manager.validate_paths()
        
        self.assertIsInstance(validation_results, dict)
        
        # 모든 결과가 boolean인지 확인
        for key, result in validation_results.items():
            self.assertIsInstance(result, bool)
    
    def test_get_environment_config(self):
        """환경 설정 통합 테스트"""
        env_config = self.config_manager.get_environment_config()
        
        self.assertIsInstance(env_config, dict)
        
        # 반환되는 키들이 문자열인지 확인
        for key, value in env_config.items():
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)


class TestConfigManagerSingleton(unittest.TestCase):
    """ConfigManager 싱글톤 테스트"""
    
    def test_singleton_behavior(self):
        """싱글톤 동작 테스트"""
        # 같은 인스턴스 반환 확인
        manager1 = get_config_manager()
        manager2 = get_config_manager()
        
        self.assertIs(manager1, manager2)
    
    def test_singleton_with_custom_path(self):
        """커스텀 경로로 새 인스턴스 생성 테스트"""
        # 기본 인스턴스
        default_manager = get_config_manager()
        
        # 임시 설정 파일 생성
        temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump({'test': 'value'}, temp_config, allow_unicode=True)
        temp_config.close()
        
        try:
            # 커스텀 경로로 새 인스턴스
            custom_manager = get_config_manager(temp_config.name)
            
            # 다른 인스턴스여야 함
            self.assertIsNot(default_manager, custom_manager)
            
        finally:
            # 정리
            if os.path.exists(temp_config.name):
                os.unlink(temp_config.name)


if __name__ == '__main__':
    # 테스트 실행
    unittest.main(verbosity=2)