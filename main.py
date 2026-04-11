import os
import json
import math
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
LOCATIONS_FILE = MEMORY_DIR / "locations.json"

REVISIT_PROBABILITY = 0.1  # 10%の確率で過去の場所の近くを再訪
NEARBY_THRESHOLD_KM = 2.0  # この距離以内なら「近い場所」と判定


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


def haversine_km(lat1, lon1, lat2, lon2):
    """2地点間の距離をキロメートルで返す"""
    r = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_locations():
    """過去の観測地点を読み込む"""
    if LOCATIONS_FILE.exists():
        with open(LOCATIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_locations(locations):
    """観測地点を保存する"""
    with open(LOCATIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(locations, f, ensure_ascii=False, indent=2)


def find_nearby_past_locations(lat, lon, locations):
    """現在地の近くにある過去の観測地点を探す"""
    nearby = []
    for loc in locations:
        dist = haversine_km(lat, lon, loc["lat"], loc["lon"])
        if dist <= NEARBY_THRESHOLD_KM:
            nearby.append({**loc, "distance_km": round(dist, 2)})
    nearby.sort(key=lambda x: x["distance_km"])
    return nearby


def get_location_with_revisit(past_locations):
    """通常のランダム地点 or 過去の場所の近くを返す。再訪コンテキストも返す。"""
    # 過去の記録があり、確率を満たしたら再訪を試みる
    if past_locations and random.random() < REVISIT_PROBABILITY:
        target = random.choice(past_locations)
        # 元の地点から半径1km以内のランダムなずれ
        offset_lat = random.uniform(-0.009, 0.009)  # ~1km
        offset_lon = random.uniform(-0.011, 0.011)  # ~1km
        lat = target["lat"] + offset_lat
        lon = target["lon"] + offset_lon
        logging.info(f"Revisit mode: near Day {target['day']} ({target['address']})")

        # Google Maps で住所を取得
        address = resolve_address(lat, lon)
        nearby = [{"day": target["day"], "address": target["address"],
                    "distance_km": round(haversine_km(lat, lon, target["lat"], target["lon"]), 2)}]
        return lat, lon, address, nearby

    # 通常のランダム地点
    lat, lon, address = get_random_tokyo_location()
    nearby = find_nearby_past_locations(lat, lon, past_locations)
    return lat, lon, address, nearby


def resolve_address(lat, lon):
    """緯度経度から住所を取得する"""
    if not GOOGLE_MAPS_API_KEY:
        return f"緯度: {lat:.6f}, 経度: {lon:.6f} の地点"

    url = (
        f"https://maps.googleapis.com/maps/api/geocode/json"
        f"?latlng={lat},{lon}&key={GOOGLE_MAPS_API_KEY}&language=ja"
    )
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "OK" and data.get("results"):
            return data["results"][0]["formatted_address"]
    except Exception as e:
        logging.error(f"Error fetching address: {e}")
    return f"緯度: {lat:.6f}, 経度: {lon:.6f} の地点"


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


def load_revisit_diaries(nearby_locations, current_day):
    """再訪対象の日の日記を読み込む（直近7日分に含まれないもののみ）"""
    recent_start = max(1, current_day - 7)
    diaries = []
    for loc in nearby_locations:
        day = loc["day"]
        if day >= recent_start:
            continue  # 直近7日分に既に含まれているのでスキップ
        f = DAILY_LOG_DIR / f"day{day}.md"
        if f.exists():
            content = read_file(f)
            diaries.append(f"#### Day {day} の日記（再訪参照）\n{content}")
    return "\n\n".join(diaries) if diaries else ""


def build_prompt(current_day, address, character, knowledge, emotional_log, past_diaries, nearby_locations):
    """メインプロンプトを構築する"""
    revisit_context = ""
    revisit_diaries = ""
    if nearby_locations:
        lines = []
        for loc in nearby_locations:
            lines.append(f"  - Day {loc['day']} の観測地点「{loc['address']}」（約{loc['distance_km']}km先）")
        revisit_context = (
            "\n- **再訪の手がかり**: 本日の観測地点は、過去に訪れた場所の近くです。\n"
            + "\n".join(lines)
            + "\n  あの日と同じ場所の変化、あるいは同じ街の別の表情を意識して観測してください。"
        )
        revisit_diaries = load_revisit_diaries(nearby_locations, current_day)

    revisit_section = ""
    if revisit_diaries:
        revisit_section = f"\n\n### 再訪地点の過去の日記\n{revisit_diaries}"

    return f"""あなたは以下のキャラクター設定に**完全に**従って日記を書きます。
    設定から逸脱しないでください。特に「成長のフェーズ」と「絶対に守るルール」を厳守してください。

    {character}

---

## 本日の情報
- **Day {current_day}**
- **観測地点**: {address}{revisit_context}

---

## これまでの全記録
### 過去の観察日記
{past_diaries if past_diaries else "（これが最初の観察です）"}{revisit_section}

### 蓄積された人間の法則
{knowledge.strip() if knowledge.strip() else "（まだ蓄積された法則はありません）"}

### 観測者の内面記録
{emotional_log.strip() if emotional_log.strip() else "（まだ内面の変化は記録されていません）"}

---

## フェーズ判定指示

日記を書く前に、まず「観測者の内面記録」をすべて読み返してください。
そして、キャラクター設定の「成長のフェーズ」に照らし合わせ、今のノアがどのフェーズにいるかを判断してください。
判断の根拠（どの内面記録のどの部分が、どのフェーズの特徴に該当するか）を明確にしてください。
フェーズは必ず前回と同じか、一つだけ進むかのどちらかです。一度に二つ以上進むことはありません。

---

## 出力指示

必ず以下の4つのセクションすべてを、指定された見出しの順番通りに完全に出力してください。
日記を書き終えた後も、絶対に途中で出力を打ち切らず、セクション4まで書き切ってください。
Markdownで、余分なテキスト（「```markdown」等）は省き、直接見出しから始めてください。

### セクション1: フェーズ判定
`## フェーズ判定` から書き始めてください。

以下を記録してください：
- **現在のフェーズ**: Phase X: フェーズ名
- **判定根拠**: 内面記録のどの蓄積から、このフェーズにいると判断したか（2〜3行）
- **次のフェーズへの距離**: 次のフェーズの兆候がどの程度現れているか（まだ遠い／兆候が見え始めている／もう間もなく）

### セクション2: 本日の観察日記
`# Day {current_day}: 観察記録（{address}）` から書き始めてください。

注意点：
- 過去の日記で登場した場所・人物・出来事に関連があれば、必ず言及すること
- 現在のフェーズにふさわしい内面の変化を、描写の端々に滲ませること
- 過去に立てた「人間の法則」に関連する場面があれば、その法則を引用し、確認・修正・深化させること
- 現在のフェーズにふさわしい観測者の距離感で書くこと
- 季節の描写を自然に織り込むこと
- 400字程度で書くこと

### セクション3: 新しく学んだ／修正した人間の法則
`## 新しく学んだ人間の法則` から書き始めてください。

- 新しい法則には `[Day {current_day} 新規]` のラベルをつけること
- 過去の法則を修正する場合は `[Day {current_day} 修正: 元はDay X]` のラベルをつけ、何がどう変わったか書くこと
- 該当なしの場合は「特になし」と書くこと

### セクション4: 観測者の内面変化
`## 内面記録` から書き始めてください。

以下を簡潔に（各1〜3行で）記録してください：
- **現在のフェーズ**: Phase X: フェーズ名
- **本日の核心的感覚**: 今日の観測で最も強く残った感覚を、感情語を使わず身体感覚や比喩で
- **気になった存在**: 特に目が離せなかった人間や光景（いれば）
- **自問**: 今日の観測を経て生まれた、自分自身への問い
- **前日からの変化**: 昨日の自分と今日の自分で何が違うか（Day 1なら不要）"""


def parse_output(result):
    """Claude の出力を4セクションに分割する（フェーズ判定、日記、法則、内面記録）"""
    phase = ""
    diary = result
    new_laws = ""
    emotional = ""

    # フェーズ判定セクションの分割
    if "## フェーズ判定" in result:
        parts = result.split("## フェーズ判定", 1)
        remainder = parts[1]
        # 日記セクション（"# Day"）で分割
        if "# Day" in remainder:
            phase_parts = remainder.split("# Day", 1)
            phase = phase_parts[0].strip()
            diary = "# Day" + phase_parts[1]
        else:
            phase = remainder.strip()
            diary = ""

    # 法則セクションの分割
    if "## 新しく学んだ人間の法則" in diary:
        parts = diary.split("## 新しく学んだ人間の法則", 1)
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

    return phase, diary, new_laws, emotional


def generate_diary(prompt):
    """Claude APIを呼び出して日記を生成する"""
    if not ANTHROPIC_API_KEY:
        logging.error("Anthropic API Keyが設定されていません。")
        return None

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
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

    # 場所を取得（再訪の可能性あり）
    past_locations = load_locations()
    lat, lon, address, nearby = get_location_with_revisit(past_locations)
    if nearby:
        logging.info(f"Nearby past locations: {[f'Day {n['day']} ({n['distance_km']}km)' for n in nearby]}")

    # プロンプト構築
    prompt = build_prompt(
        current_day, address, character, knowledge, emotional, past_diaries, nearby
    )

    # 生成
    logging.info(f"Calling Claude for Day {current_day}...")
    result = generate_diary(prompt)

    if not result:
        logging.error("Failed to generate the observation log.")
        return

    # 出力をパース
    phase, diary, new_laws, emotional = parse_output(result)
    if phase:
        logging.info(f"Phase assessment:\n{phase}")

    # 日記を保存
    log_filepath = DAILY_LOG_DIR / f"day{current_day}.md"
    write_file(log_filepath, diary)
    logging.info(f"Saved observation log to {log_filepath}")

    # 観測地点を記録
    past_locations.append({"day": current_day, "lat": lat, "lon": lon, "address": address})
    save_locations(past_locations)
    logging.info(f"Saved location for Day {current_day}.")

    # 法則を追記
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
