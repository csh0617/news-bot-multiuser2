import argparse
import shutil
import sys
from pathlib import Path

CATEGORIES = {
    "이미지": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".tiff", ".ico", ".heic"},
    "문서": {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".hwp", ".md"},
    "스프레드시트": {".xls", ".xlsx", ".csv", ".ods"},
    "프레젠테이션": {".ppt", ".pptx", ".odp", ".key"},
    "동영상": {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm", ".m4v"},
    "음악": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
    "압축파일": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "코드": {".py", ".js", ".ts", ".java", ".c", ".cpp", ".h", ".hpp", ".cs", ".go", ".rs", ".rb", ".php", ".html", ".css", ".sh", ".json", ".xml", ".yml", ".yaml"},
    "실행파일": {".exe", ".msi", ".dmg", ".apk", ".deb", ".rpm", ".app"},
    "폰트": {".ttf", ".otf", ".woff", ".woff2"},
}


def category_for(ext: str) -> str:
    ext = ext.lower()
    for name, exts in CATEGORIES.items():
        if ext in exts:
            return name
    return "기타"


def unique_path(target: Path) -> Path:
    if not target.exists():
        return target
    stem, suffix, parent = target.stem, target.suffix, target.parent
    i = 1
    while True:
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def organize(src: Path, dry_run: bool = False, recursive: bool = False) -> dict:
    if not src.exists() or not src.is_dir():
        raise NotADirectoryError(f"대상 폴더가 존재하지 않습니다: {src}")

    stats: dict[str, int] = {}
    script_path = Path(__file__).resolve()
    category_dirs = {src / name for name in list(CATEGORIES.keys()) + ["기타"]}

    files = src.rglob("*") if recursive else src.iterdir()
    for entry in files:
        if not entry.is_file():
            continue
        if entry.resolve() == script_path:
            continue
        if any(parent in category_dirs for parent in entry.parents):
            continue

        category = category_for(entry.suffix)
        dest_dir = src / category
        dest = unique_path(dest_dir / entry.name)

        print(f"[{'DRY' if dry_run else 'MOVE'}] {entry.relative_to(src)} → {category}/{dest.name}")

        if not dry_run:
            dest_dir.mkdir(exist_ok=True)
            shutil.move(str(entry), str(dest))

        stats[category] = stats.get(category, 0) + 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="파일 확장자에 따라 폴더를 정리합니다.")
    parser.add_argument("path", nargs="?", default=".", help="정리할 폴더 경로 (기본: 현재 폴더)")
    parser.add_argument("--dry-run", action="store_true", help="실제 이동 없이 계획만 출력")
    parser.add_argument("--recursive", "-r", action="store_true", help="하위 폴더까지 포함")
    args = parser.parse_args()

    target = Path(args.path).expanduser().resolve()
    print(f"[*] 폴더 정리 시작: {target}")
    if args.dry_run:
        print("[*] DRY RUN 모드 - 실제 이동은 하지 않습니다.")

    try:
        stats = organize(target, dry_run=args.dry_run, recursive=args.recursive)
    except NotADirectoryError as e:
        print(f"[에러] {e}")
        return 1

    print("\n[요약]")
    if not stats:
        print("  정리할 파일이 없습니다.")
    else:
        for category, count in sorted(stats.items(), key=lambda x: -x[1]):
            print(f"  {category}: {count}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
