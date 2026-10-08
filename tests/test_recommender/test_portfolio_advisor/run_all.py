"""
portfolio_advisor 全部测试总入口（自定义 runner 模式，非 pytest）

依次运行 test_portfolio_advisor 目录下所有测试文件。

用法：
    python tests/test_recommender/test_portfolio_advisor/run_all.py
"""
import importlib.util
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(project_root))

# Windows 控制台 GBK 无法输出 emoji，统一改为 UTF-8（与 app/__main__.py 一致）
# 注意：被加载的测试模块也会做同样检查，已包装则跳过，避免双重包装关闭底层 buffer
if sys.platform == "win32" and sys.stdout.encoding != "utf-8":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

TEST_DIR = Path(__file__).resolve().parent
TEST_FILES = ["test_utils.py", "test_dimension.py", "test_rebalance.py",
              "test_stress.py", "test_format.py"]


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载测试模块: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    all_ok = True
    for filename in TEST_FILES:
        path = TEST_DIR / filename
        module = _load_module(path)
        print("#" * 70)
        print(f"# {filename}")
        print("#" * 70)
        ok = module.run_all_tests()
        all_ok = all_ok and ok
        print()
    print("=" * 70)
    print("总体结果:", "全部通过 ✅" if all_ok else "存在失败 ❌")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
