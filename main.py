import os
import random
import logging
import re
from pathlib import Path
from dotenv import load_dotenv
import requests
import anthropic

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
DAILY_LOG_DIR = MEMORY_DIR / "daily_log"
CHARACTER_FILE = MEMORY_DIR / "character.md"
KNOWLEDGE_FILE = MEMORY_DIR / "knowledge.md"
EMOTIONAL_FILE = MEMORY_DIR / "emotional.md"


def get_random_tokyo_location():
    """東京のランダムな緯度経度を生成し、Google Maps APIで住所情報を取得する"""
    lat = random.uniform(35.5, 35.8)
    lon = random.uniform(139.5, 139.9)
    logging.info(f"Generated coordinates: {lat:.6f}, {lon:.6f}")

    if not GOOGLE_MAPS_API_KEY:
        logging.warning("Google Maps API Keyが設定されていません。座標のみを返します。")
        return lat, lon, f"緯度: {lat:.6f}, 経度: {lon:.6f} の地点"

    url = (
        f"https://maps.googleapis.com/maps/api/geocode/json"
        f"?latlng={lat},{lon}&key={GOOGLE_MAPS_API_KEY}&language=ja"
    )
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "OK" and data.get("results"):
            address = data["results"][0]["formatted_address"]
            logging.info(f"Target location acquired: {address}")
            return lat, lon, address
        else:
            logging.warning(f"Geocoding failed. Status: {data.get('status')}")
            return lat, lon, f"緯度: {lat:.6f}, 経度: {lon:.6f} の地点"
    except Exception as e:
        logging.error(f"Error fetching address from Google Maps API: {e}")
        return lat, lon, f"緯度: {lat:.6f}, 経度: {lon:.6f} の地点"


def read_file(filepath):
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def write_file(filepath, content):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


def append_file(filepath, content):
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(content)


def get_current_day():
    """既存の dayX.md ファイルから今の「Day」を計算する"""
    days = []
    if DAILY_LOG_DIR.exists():
        for file in DAILY_LOG_DIR.glob("day*.md"):
            match = re.search(r"day(\d+)\.md", file.name)
            if match:
                days.append(int(match.group(1)))
    last_day = max(days) if days else 0
    return last_day + 1, last_day


def load_all_past_diaries(current_day):
    """過去の日記を全件読み込んで連結する(直近7日間が最大)"""
    entries = []
    start_day = max(1, current_day - 7) #直近7日間

    for d in range(start_day, current_day):
        f = DAILY_LOG_DIR / f"day{d}.md"
        if f.exists():
            entries.append(read_file(f))
    return "\n\n---\n\n".join(entries) if entries else ""


def build_prompt(current_day, address, character, knowledge, emotional_log, past_diaries):
    """メインプロンプトを構築する"""
    return f"""あなたは以下のキャラクター設定に**完全に**従って日記を書きます。
    設定から逸脱しないでください。特に「成長の曲線」と「絶対に守るルール」を厳守してください。

    {character}

---

## 本日の情報
- **Day {current_day} / 7**（観測任務は全7日間）
- **観測地点**: {address}

---

## これまでの全記録
### 過去の観察日記
{past_diaries if past_diaries else "（これが最初の観察です）"}

### 蓄積された人間の法則
{knowledge.strip() if knowledge.strip() else "（まだ蓄積された法則はありません）"}

### 観測者の内面記録
{emotional_log.strip() if emotional_log.strip() else "（まだ内面の変化は記録されていません）"}

---

## 出力指示

以下の3つのセクションを、この順番で出力してください。
Markdownで、余分なテキスト（「```markdown」等）は省き、直接見出しから始めてください。

### セクション1: 本日の観察日記
`# Day {current_day}: 観察記録` から書き始めてください。

注意点：
- 過去の日記で登場した場所・人物・出来事に関連があれば、必ず言及すること
- 「成長の曲線」に沿った内面の変化を、描写の端々に滲ませること
- 過去に立てた「人間の法則」に関連する場面があれば、その法則を引用し、確認・修正・深化させること
- Day {current_day} にふさわしい観測者の距離感で書くこと
- 400字程度で書くこと

### セクション2: 新しく学んだ／修正した人間の法則
`## 新しく学んだ人間の法則` から書き始めてください。

- 新しい法則には `[Day {current_day} 新規]` のラベルをつけること
- 過去の法則を修正する場合は `[Day {current_day} 修正: 元はDay X]` のラベルをつけ、何がどう変わったか書くこと
- 該当なしの場合は「特になし」と書くこと

### セクション3: 観測者の内面変化
`## 内面記録` から書き始めてください。

以下を簡潔に（各1〜3行で）記録してください：
- **本日の核心的感覚**: 今日の観測で最も強く残った感覚を、感情語を使わず身体感覚や比喩で
- **気になった存在**: 特に目が離せなかった人間や光景（いれば）
- **自問**: 今日の観測を経て生まれた、自分自身への問い
- **前日からの変化**: 昨日の自分と今日の自分で何が違うか（Day 1なら不要）"""


def parse_output(result):
    """Claude の出力を3セクションに分割する"""
    diary = result
    new_laws = ""
    emotional = ""

    # 法則セクションの分割
    if "## 新しく学んだ人間の法則" in result:
        parts = result.split("## 新しく学んだ人間の法則", 1)
        diary = parts[0].strip()
        remainder = parts[1]
    else:
        remainder = ""

    # 内面記録セクションの分割
    if "## 内面記録" in remainder:
        law_parts = remainder.split("## 内面記録", 1)
        new_laws = law_parts[0].strip()
        emotional = law_parts[1].strip()
    elif "## 内面記録" in diary:
        diary_parts = diary.split("## 内面記録", 1)
        diary = diary_parts[0].strip()
        emotional = diary_parts[1].strip()
    else:
        new_laws = remainder.strip()

    return diary, new_laws, emotional


def generate_diary(prompt):
    """Claude APIを呼び出して日記を生成する"""
    if not ANTHROPIC_API_KEY:
        logging.error("Anthropic API Keyが設定されていません。")
        return None

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-6-20250514",
            max_tokens=4096,
            temperature=0.6,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        logging.error(f"Error communicating with Claude API: {e}")
        return None


def main():
    logging.info("--- Starting Autonomous AI Observer ---")

    DAILY_LOG_DIR.mkdir(parents=True, exist_ok=True)

    # 各種ファイル読み込み
    character = read_file(CHARACTER_FILE)
    if not character:
        logging.error("character.md が存在しません。終了します。")
        return

    knowledge = read_file(KNOWLEDGE_FILE)
    if not knowledge:
        logging.error("knowledge.md が存在しません。終了します。")
        return

    emotional = read_file(EMOTIONAL_FILE)
    if not emotional:
        logging.error("character.md が存在しません。終了します。")
        return


    # 現在の日を計算
    current_day, _ = get_current_day()
    logging.info(f"Executing for Day: {current_day}")

    # 過去の全日記を読み込み
    past_diaries = load_all_past_diaries(current_day)

    # 場所を取得
    _, _, address = get_random_tokyo_location()

    # プロンプト構築
    prompt = build_prompt(
        current_day, address, character, knowledge, emotional, past_diaries
    )

    # 生成
    logging.info(f"Calling Claude for Day {current_day}...")
    result = generate_diary(prompt)

    if not result:
        logging.error("Failed to generate the observation log.")
        return

    # 出力をパース
    diary, new_laws, emotional = parse_output(result)

    # 日記を保存
    log_filepath = DAILY_LOG_DIR / f"day{current_day}.md"
    write_file(log_filepath, diary)
    logging.info(f"Saved observation log to {log_filepath}")

    # 知識記録を追記
    if new_laws and "特になし" not in new_laws:
        header = f"\n\n### Day {current_day}（{address}）\n"
        append_file(KNOWLEDGE_FILE, header + new_laws + "\n")
        logging.info("Updated knowledge.md.")

    # 内面記録を追記
    if emotional:
        header = f"\n\n### Day {current_day}\n"
        append_file(EMOTIONAL_FILE, header + emotional + "\n")
        logging.info("Updated emotional_log.md.")

    logging.info(f"--- Day {current_day} Complete ---")


if __name__ == "__main__":
    main()
