"""main.py の実行で生成・追記されたデータを初期状態に戻すスクリプト"""

import shutil
from pathlib import Path

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
DAILY_LOG_DIR = MEMORY_DIR / "daily_log"
KNOWLEDGE_FILE = MEMORY_DIR / "knowledge.md"
EMOTIONAL_FILE = MEMORY_DIR / "emotional.md"

KNOWLEDGE_INITIAL = """\
# 蓄積された人間の法則

※ここには観測者が日々の観察を通じて学習した「人間の生態や心理の法則」が蓄積されていきます。
※法則は追加だけでなく、後日の観察で修正・撤回されることもあります。
"""

EMOTIONAL_INITIAL = """\
# 観測者の内面記録

※ここには観測者が日々感じた内面の変化、気になった存在、自問、戸惑いなどが蓄積されていきます。
"""


def main():
    # daily_log 内のファイルを全削除
    if DAILY_LOG_DIR.exists():
        count = 0
        for f in DAILY_LOG_DIR.iterdir():
            if f.is_file():
                f.unlink()
                count += 1
        print(f"daily_log: {count} 件のファイルを削除しました")
    else:
        print("daily_log: ディレクトリが存在しません（スキップ）")

    # knowledge.md を初期状態に戻す
    KNOWLEDGE_FILE.write_text(KNOWLEDGE_INITIAL, encoding="utf-8")
    print("knowledge.md: 初期状態に戻しました")

    # emotional.md を初期状態に戻す
    EMOTIONAL_FILE.write_text(EMOTIONAL_INITIAL, encoding="utf-8")
    print("emotional.md: 初期状態に戻しました")

    print("クリーンアップ完了!")


if __name__ == "__main__":
    main()
