import os
import random
import logging
import re
from pathlib import Path
from dotenv import load_dotenv
import requests
import anthropic

# ログ設定（デバッグ・進捗確認用）
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 環境変数の読み込み
load_dotenv()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

BASE_DIR = Path(__file__).parent
MEMORY_DIR = BASE_DIR / "memory"
DAILY_LOG_DIR = MEMORY_DIR / "daily_log"
CHARACTER_FILE = MEMORY_DIR / "character.md"
KNOWLEDGE_FILE = MEMORY_DIR / "knowledge.md"

def get_random_tokyo_location():
    """
    東京のランダムな緯度経度を生成し、Google Maps APIで住所情報を取得する
    """
    # 東京の概ねのバウンディングボックス（緯度 35.5 ~ 35.8, 経度 139.5 ~ 139.9）
    lat = random.uniform(35.5, 35.8)
    lon = random.uniform(139.5, 139.9)
    logging.info(f"Generated coordinates: {lat:.6f}, {lon:.6f}")
    
    if not GOOGLE_MAPS_API_KEY:
        logging.warning("Google Maps API Keyが設定されていません。座標のみを返します。")
        return lat, lon, f"緯度: {lat:.6f}, 経度: {lon:.6f} の地点"

    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={GOOGLE_MAPS_API_KEY}&language=ja"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get('status') == 'OK' and data.get('results'):
            address = data['results'][0]['formatted_address']
            logging.info(f"Target location acquired: {address}")
            return lat, lon, address
        else:
            logging.warning(f"Geocoding failed. Status: {data.get('status')}. Using coordinates only.")
            return lat, lon, f"緯度: {lat:.6f}, 経度: {lon:.6f} の地点"
    except Exception as e:
        logging.error(f"Error fetching address from Google Maps API: {e}")
        return lat, lon, f"緯度: {lat:.6f}, 経度: {lon:.6f} の地点"

def read_file(filepath):
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    return ""

def write_file(filepath, content):
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

def get_current_day():
    """
    既存の dayX.md ファイルから今の「Day」を計算する
    """
    days = []
    if DAILY_LOG_DIR.exists():
        for file in DAILY_LOG_DIR.glob("day*.md"):
            match = re.search(r"day(\d+)\.md", file.name)
            if match:
                days.append(int(match.group(1)))
    last_day = max(days) if days else 0
    return last_day + 1, last_day

def generate_diary(current_day, address, character_prompt, knowledge, past_diary):
    """
    Claude APIを呼び出して当日の日記と新しい法則を生成する
    """
    if not ANTHROPIC_API_KEY:
        logging.error("Anthropic API Keyが設定されていません。")
        return None

    logging.info(f"Calling Claude for Day {current_day} observation...")
    
    prompt = f"""
あなたは以下の設定を持つ「異世界から来た観測者」です。
{character_prompt}

【本日の観測地点】
{address}

【これまでに蓄積した人間の法則】
{knowledge if knowledge and knowledge.strip() else "まだ蓄積された法則はありません。"}

【前日の記録】
{past_diary if past_diary else "これが最初の観察になります。"}

上記を踏まえ、以下の2点を出力してください。
出力形式はMarkdownで、タグなどの余分なテキストは省き、直接見出しから始めてください。

1. 本日の観察日記
(Markdownの見出し `# Day {current_day}: 観察記録` から書き始めてください)

2. 新しく学んだ人間の法則
(Markdownの見出し `## 新しく学んだ人間の法則` から書き始めてください。もしその日の観察で新しく学んだ真理や法則がなければ「特になし」で構いません)
"""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.content[0].text
        logging.info("Successfully generated diary via Claude.")
        return content
    except Exception as e:
        logging.error(f"Error communicating with Claude API: {e}")
        return None

def main():
    logging.info("--- Starting Autonomous AI Observer ---")
    
    # フォルダが存在しない場合は作成
    DAILY_LOG_DIR.mkdir(parents=True, exist_ok=True)
    
    # キャラクター設定と既存の知識を読み込む
    if not CHARACTER_FILE.exists():
        logging.warning("character.md が存在しません。基本設定ファイルを確認してください。")
        character_prompt = "あなたは異世界から来た観測者です。"
    else:
        character_prompt = read_file(CHARACTER_FILE)
        
    knowledge = read_file(KNOWLEDGE_FILE)
    
    # 現在の日にちを計算
    current_day, last_day = get_current_day()
    logging.info(f"Executing for Day: {current_day}")
    
    # 前日の日記を取得（コンテキストとして使用）
    past_diary = ""
    if last_day > 0:
        past_diary_file = DAILY_LOG_DIR / f"day{last_day}.md"
        past_diary = read_file(past_diary_file)
        
    # 位置情報を取得
    lat, lon, address = get_random_tokyo_location()
    
    # ClaudeへAPIリクエスト
    result = generate_diary(current_day, address, character_prompt, knowledge, past_diary)
    
    if result:
        # 結果のパース: 観察日記部分と新しい法則部分を分割
        parts = result.split("## 新しく学んだ人間の法則")
        diary_part = parts[0].strip()
        new_laws_part = parts[1].strip() if len(parts) > 1 else ""
        
        # 日記をファイルに保存
        log_filepath = DAILY_LOG_DIR / f"day{current_day}.md"
        write_file(log_filepath, diary_part)
        logging.info(f"Saved observation log to {log_filepath}")
        
        # 新しい法則があれば knowledge.md を更新
        if new_laws_part and "特になし" not in new_laws_part:
            header = f"\n\n### Day {current_day} (場所: {lat:.4f}, {lon:.4f}) の気づき\n"
            added_knowledge = header + new_laws_part
            new_knowledge = knowledge + added_knowledge
            write_file(KNOWLEDGE_FILE, new_knowledge.strip())
            logging.info("Updated knowledge.md with new observations.")
        else:
            logging.info("No new laws to add today.")
    else:
        logging.error("Failed to generate the observation log.")
        
    logging.info("--- Finished Autonomous AI Observer ---")

if __name__ == "__main__":
    main()
