#!/usr/bin/env python3
"""
플랫폼 유틸리티 테스트 모듈
"""

import unittest
import sys
import os
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from utils.platform_utils import (
    PlatformInfo, 
    PathManager, 
    EnvironmentManager,
    CommandExecutor,
    get_platform_manager
)


class TestPlatformInfo(unittest.TestCase):
    """PlatformInfo 테스트"""
    
    def setUp(self):
        self.platform_info = PlatformInfo()
    
    def test_platform_detection(self):
        """플랫폼 감지 테스트"""
        # 플랫폼 ID가 유효한 값인지 확인
        valid_platforms = ['windows', 'wsl', 'macos', 'linux', 'unknown']
        self.assertIn(self.platform_info.platform_id, valid_platforms)
        
        # 시스템 정보가 설정되어 있는지 확인
        self.assertIsNotNone(self.platform_info.system)
        
        # Boolean 플래그들이 올바르게 설정되어 있는지 확인
        flags = [
            self.platform_info.is_windows,
            self.platform_info.is_mac,
            self.platform_info.is_linux,
            self.platform_info.is_wsl
        ]
        
        # 적어도 하나의 플래그는 True여야 함 (unknown 제외)
        if self.platform_info.platform_id != 'unknown':
            self.assertTrue(any(flags))
    
    def test_to_dict(self):
        """딕셔너리 변환 테스트"""
        info_dict = self.platform_info.to_dict()
        
        required_keys = [
            'system', 'platform_id', 'is_windows', 
            'is_mac', 'is_linux', 'is_wsl'
        ]
        
        for key in required_keys:
            self.assertIn(key, info_dict)


class TestPathManager(unittest.TestCase):
    """PathManager 테스트"""
    
    def setUp(self):
        self.platform_info = PlatformInfo()
        self.path_manager = PathManager(self.platform_info)
    
    def test_windows_path_conversion(self):
        """Windows 경로 변환 테스트"""
        test_cases = [
            ("C:\\Users\\test\\file.txt", "C:", "test/file.txt"),
            ("D:\\Projects\\LawPass", "D:", "Projects/LawPass"),
            ("E:\\Data\\files", "E:", "Data/files"),
        ]
        
        for windows_path, expected_drive, expected_path in test_cases:
            converted = self.path_manager.convert_windows_path(windows_path)
            
            # 결과가 문자열인지 확인
            self.assertIsInstance(converted, str)
            
            # 변환된 경로가 원본과 다른지 확인 (WSL/macOS/Linux에서)
            if not self.platform_info.is_windows:
                self.assertNotEqual(converted, windows_path)
    
    def test_normalize_path(self):
        """경로 정규화 테스트"""
        test_paths = [
            ".",
            "..",
            "./test/../file.txt",
            str(Path.home())
        ]
        
        for path in test_paths:
            normalized = self.path_manager.normalize_path(path)
            self.assertIsInstance(normalized, str)
            self.assertTrue(os.path.isabs(normalized))
    
    def test_validate_path(self):
        """경로 유효성 검사 테스트"""
        # 존재하는 경로 테스트 (홈 디렉토리)
        home_path = str(Path.home())
        self.assertTrue(self.path_manager.validate_path(home_path))
        
        # 존재하지 않는 경로 테스트
        fake_path = "/this/path/should/not/exist/12345"
        self.assertFalse(self.path_manager.validate_path(fake_path))


class TestEnvironmentManager(unittest.TestCase):
    """EnvironmentManager 테스트"""
    
    def setUp(self):
        self.platform_info = PlatformInfo()
        self.env_manager = EnvironmentManager(self.platform_info)
    
    def test_get_platform_env(self):
        """플랫폼별 환경 변수 테스트"""
        # PATH 환경 변수는 모든 시스템에 존재해야 함
        path_var = self.env_manager.get_platform_env('PATH')
        self.assertIsInstance(path_var, str)
        self.assertGreater(len(path_var), 0)
        
        # 존재하지 않는 환경 변수
        fake_var = self.env_manager.get_platform_env('FAKE_VAR_12345', 'default')
        self.assertEqual(fake_var, 'default')
    
    def test_set_platform_env(self):
        """환경 변수 설정 테스트"""
        test_var = 'TEST_PLATFORM_VAR'
        test_value = 'test_value_12345'
        
        # 환경 변수 설정
        self.env_manager.set_platform_env(test_var, test_value)
        
        # 설정된 값 확인
        retrieved_value = self.env_manager.get_platform_env(test_var)
        self.assertEqual(retrieved_value, test_value)
        
        # 정리
        if test_var in os.environ:
            del os.environ[test_var]


class TestCommandExecutor(unittest.TestCase):
    """CommandExecutor 테스트"""
    
    def setUp(self):
        self.platform_info = PlatformInfo()
        self.cmd_executor = CommandExecutor(self.platform_info)
    
    def test_get_npm_command(self):
        """npm 명령어 테스트"""
        npm_cmd = self.cmd_executor.get_npm_command()
        
        if self.platform_info.is_windows:
            self.assertEqual(npm_cmd, "npm.cmd")
        else:
            self.assertEqual(npm_cmd, "npm")
    
    def test_copy_to_clipboard_safety(self):
        """클립보드 복사 안전성 테스트 (실제 복사는 하지 않음)"""
        # 빈 문자열 테스트
        result = self.cmd_executor.copy_to_clipboard("")
        # 결과가 boolean인지만 확인 (실제 클립보드 수정은 위험)
        self.assertIsInstance(result, bool)


class TestPlatformManagerIntegration(unittest.TestCase):
    """PlatformManager 통합 테스트"""
    
    def setUp(self):
        self.platform_manager = get_platform_manager()
    
    def test_manager_initialization(self):
        """매니저 초기화 테스트"""
        self.assertIsNotNone(self.platform_manager.info)
        self.assertIsNotNone(self.platform_manager.path)
        self.assertIsNotNone(self.platform_manager.env)
        self.assertIsNotNone(self.platform_manager.cmd)
    
    def test_get_default_config_paths(self):
        """기본 설정 경로 테스트"""
        config_paths = self.platform_manager.get_default_config_paths()
        
        required_keys = ['config_dir', 'documents', 'downloads', 'temp']
        for key in required_keys:
            self.assertIn(key, config_paths)
            self.assertIsInstance(config_paths[key], str)
    
    def test_should_use_parallel_processing(self):
        """병렬 처리 가능 여부 테스트"""
        result = self.platform_manager.should_use_parallel_processing()
        self.assertIsInstance(result, bool)
        
        # Windows에서는 False여야 함
        if self.platform_manager.info.is_windows:
            self.assertFalse(result)


if __name__ == '__main__':
    # 테스트 실행
    unittest.main(verbosity=2)