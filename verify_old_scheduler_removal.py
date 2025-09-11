#!/usr/bin/env python3
"""
验证旧调度器代码是否完全移除

此脚本检查项目中是否还有任何对旧 APScheduler 调度器的引用，
确保成功迁移到新的 RayScheduler。
"""

import os
import re
from pathlib import Path


def search_old_scheduler_references(project_root: str) -> dict[str, list[str]]:
    """搜索旧调度器的引用"""
    old_scheduler_patterns = [
        r"apscheduler",
        r"APScheduler",
        r"USE_RAY_SCHEDULER",
        r"SchedulerAdapter",
        r"from.*scheduling\.",
        r"import.*scheduling\.",
        r"\.scheduling\.",
    ]

    # 要排除的文件/目录
    excluded_paths = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
        "build",
        "dist",
        ".idea",
        ".vscode",
        "verify_old_scheduler_removal.py",  # 排除此脚本本身
    }

    results = {}

    def should_exclude(path: Path) -> bool:
        """检查路径是否应该被排除"""
        for part in path.parts:
            if part in excluded_paths:
                return True
        return False

    for root, dirs, files in os.walk(project_root):
        root_path = Path(root)

        # 修改 dirs 以排除不需要搜索的目录
        dirs[:] = [d for d in dirs if d not in excluded_paths]

        if should_exclude(root_path):
            continue

        for file in files:
            if not file.endswith((".py", ".md", ".txt", ".yaml", ".yml", ".json")):
                continue

            file_path = root_path / file

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                matches = []
                for i, line in enumerate(content.splitlines(), 1):
                    for pattern in old_scheduler_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            matches.append(f"Line {i}: {line.strip()}")

                if matches:
                    results[str(file_path)] = matches

            except (UnicodeDecodeError, PermissionError):
                # 跳过无法读取的文件
                continue

    return results


def main():
    """主函数"""
    project_root = "/Volumes/ssd/Code/ray_info_2025"

    print("🔍 搜索旧调度器相关代码...")
    print(f"📁 搜索目录: {project_root}")
    print()

    results = search_old_scheduler_references(project_root)

    if not results:
        print("✅ 成功！未发现任何旧调度器相关代码")
        print("🎉 旧调度器已完全移除，迁移到 RayScheduler 完成")
        return

    print("⚠️ 发现以下旧调度器相关代码:")
    print()

    for file_path, matches in results.items():
        print(f"📄 {file_path}")
        for match in matches:
            print(f"   {match}")
        print()

    print(f"🔍 总计发现 {len(results)} 个文件包含旧调度器相关代码")
    print("💡 建议手动检查这些文件，确保代码的正确性")


if __name__ == "__main__":
    main()
