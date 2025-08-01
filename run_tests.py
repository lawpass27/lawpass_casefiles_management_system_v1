#!/usr/bin/env python3
"""
크로스 플랫폼 테스트 실행 스크립트
"""

import unittest
import sys
import os
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def run_all_tests():
    """모든 테스트 실행"""
    
    print("🧪 크로스 플랫폼 호환성 테스트 시작\n")
    
    # 테스트 디스커버리
    test_dir = project_root / 'tests'
    loader = unittest.TestLoader()
    suite = loader.discover(str(test_dir), pattern='test_*.py')
    
    # 테스트 실행
    runner = unittest.TextTestRunner(verbosity=2, buffer=True)
    result = runner.run(suite)
    
    # 결과 요약
    print("\n" + "="*60)
    print("📊 테스트 결과 요약")
    print("="*60)
    
    print(f"총 테스트 수: {result.testsRun}")
    print(f"성공: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"실패: {len(result.failures)}")
    print(f"오류: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ 실패한 테스트:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\n💥 오류가 발생한 테스트:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    # 현재 플랫폼 정보 출력
    try:
        from utils.platform_utils import get_platform_info
        platform_info = get_platform_info()
        
        print(f"\n🖥️  테스트 환경 정보:")
        print(f"  - 시스템: {platform_info.system}")
        print(f"  - 플랫폼 ID: {platform_info.platform_id}")
        print(f"  - Windows: {platform_info.is_windows}")
        print(f"  - WSL: {platform_info.is_wsl}")
        print(f"  - macOS: {platform_info.is_mac}")
        print(f"  - Linux: {platform_info.is_linux}")
        
    except ImportError as e:
        print(f"\n⚠️  플랫폼 정보를 가져올 수 없습니다: {e}")
    
    print("\n" + "="*60)
    
    # 성공 여부 반환
    return result.wasSuccessful()


def run_specific_test(test_module):
    """특정 테스트 모듈 실행"""
    
    print(f"🧪 {test_module} 테스트 실행\n")
    
    try:
        # 테스트 모듈 로드
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromName(f'tests.{test_module}')
        
        # 테스트 실행
        runner = unittest.TextTestRunner(verbosity=2, buffer=True)
        result = runner.run(suite)
        
        return result.wasSuccessful()
        
    except Exception as e:
        print(f"❌ 테스트 실행 중 오류 발생: {e}")
        return False


def show_help():
    """도움말 표시"""
    print("크로스 플랫폼 테스트 실행 스크립트")
    print("\n사용법:")
    print("  python run_tests.py                    # 모든 테스트 실행")
    print("  python run_tests.py test_platform_utils # 특정 테스트 모듈 실행")
    print("  python run_tests.py --help             # 도움말 표시")
    print("\n사용 가능한 테스트 모듈:")
    
    test_dir = project_root / 'tests'
    if test_dir.exists():
        for test_file in test_dir.glob('test_*.py'):
            module_name = test_file.stem
            print(f"  - {module_name}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] in ['--help', '-h']:
            show_help()
            sys.exit(0)
        else:
            # 특정 테스트 모듈 실행
            test_module = sys.argv[1]
            if not test_module.startswith('test_'):
                test_module = f'test_{test_module}'
            
            success = run_specific_test(test_module)
            sys.exit(0 if success else 1)
    else:
        # 모든 테스트 실행
        success = run_all_tests()
        sys.exit(0 if success else 1)