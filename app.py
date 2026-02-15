import json, os, logging
from flask import Flask, render_template_string, request, jsonify

# .env ファイルから設定を読み込む
def load_env(path='.env'):
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, _, value = line.partition('=')
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# In-memory data store (簡易版なのでファイルベースのJSON)
DATA_FILE = 'schedule_data.json'

# Google Sheets 連携設定（.env または環境変数で指定、未設定ならSheets同期はスキップ）
GOOGLE_SHEETS_ID = os.environ.get('GOOGLE_SHEETS_ID', '')
GOOGLE_SHEETS_CREDENTIALS = os.environ.get('GOOGLE_SHEETS_CREDENTIALS', 'credentials.json')

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'family': {
            'papa': {'name': 'パパ', 'info': '会社員'},
            'mama': {'name': 'ママ', 'info': '平日勤務'},
            'sister': {'name': '第一子', 'birthday': '2023-04-10', 'info': '保育園'},
            'brother': {'name': '第二子', 'birthday': '2025-06-15', 'info': ''},
        },
        'conditions': {
            'budget': '',
            'travel_limit': '',
            'pickup_time': '',
            'weekday_available': '',
            'weekend_available': '',
        },
        'lessons': [
            {'id': 'A1', 'name': '幼児教室', 'school': '', 'address': '', 'who': 'お姉ちゃん', 'day': '', 'start': '', 'end': '', 'fee': '', 'status': '継続確定', 'memo': ''},
            {'id': 'A2', 'name': '幼児教室', 'school': '', 'address': '', 'who': '弟くん', 'day': '', 'start': '', 'end': '', 'fee': '', 'status': '継続確定', 'memo': ''},
            {'id': 'B1', 'name': 'スイミング', 'school': '', 'address': '', 'who': 'お姉ちゃん', 'day': '', 'start': '', 'end': '', 'fee': '', 'status': '継続確定', 'memo': ''},
            {'id': 'B2', 'name': 'スイミング（ベビー）', 'school': '', 'address': '', 'who': '弟くん', 'day': '', 'start': '', 'end': '', 'fee': '', 'status': '検討中', 'memo': '1歳〜が多い'},
            {'id': 'C1', 'name': 'ピアノ', 'school': '', 'address': '', 'who': 'お姉ちゃん', 'day': '', 'start': '', 'end': '', 'fee': '', 'status': '検討中', 'memo': '3歳〜が目安'},
        ],
        'patterns': {
            'A': {'name': 'パターンA', 'ids': [], 'memo': ''},
            'B': {'name': 'パターンB', 'ids': [], 'memo': ''},
            'C': {'name': 'パターンC', 'ids': [], 'memo': ''},
        }
    }

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def sync_to_sheets(data):
    """習い事候補一覧をGoogle Sheetsに同期する。未設定時やエラー時はスキップ。"""
    if not GOOGLE_SHEETS_ID:
        return
    try:
        import gspread
        gc = gspread.service_account(filename=GOOGLE_SHEETS_CREDENTIALS)
        sh = gc.open_by_key(GOOGLE_SHEETS_ID)
        try:
            ws = sh.worksheet('習い事候補')
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet(title='習い事候補', rows=100, cols=11)
        headers = ['ID', '習い事', '教室', '対象', '曜日', '開始', '終了', '月謝', '状態', 'URL', '備考']
        rows = [headers]
        for lesson in data.get('lessons', []):
            rows.append([
                lesson.get('id', ''),
                lesson.get('name', ''),
                lesson.get('school', ''),
                lesson.get('who', ''),
                lesson.get('day', ''),
                lesson.get('start', ''),
                lesson.get('end', ''),
                lesson.get('fee', ''),
                lesson.get('status', ''),
                lesson.get('url', ''),
                lesson.get('memo', ''),
            ])
        ws.clear()
        ws.update(rows, 'A1')
        logging.info('Google Sheets synced (%d lessons)', len(rows) - 1)
    except Exception as e:
        logging.warning('Google Sheets sync failed: %s', e)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>家族スケジュール計画 2026</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@300;400;500;700&family=M+PLUS+Rounded+1c:wght@400;700&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #f8f6f3;
  --card: #ffffff;
  --text: #2c2c2c;
  --text-sub: #777;
  --accent: #3b6cb4;
  --accent-light: #e8f0fe;
  --sister: #ff9a5c;
  --sister-bg: #fff3eb;
  --brother: #4ecdc4;
  --brother-bg: #e6faf8;
  --eqwel: #b07cd8;
  --eqwel-bg: #f3eafa;
  --swimming: #5b9bd5;
  --swimming-bg: #e8f2fb;
  --piano: #e88ca5;
  --piano-bg: #fdf0f3;
  --confirmed: #27ae60;
  --candidate: #f39c12;
  --reviewing: #95a5a6;
  --border: #e8e5e0;
  --shadow: 0 2px 12px rgba(0,0,0,0.06);
  --radius: 12px;
  --pattern-a: #3b6cb4;
  --pattern-b: #27ae60;
  --pattern-c: #e67e22;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: 'Noto Sans JP', sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.6;
  min-height: 100vh;
}
.app-header {
  background: linear-gradient(135deg, #2c3e6b 0%, #3b6cb4 50%, #5a9fd4 100%);
  color: white;
  padding: 24px 32px;
  position: sticky;
  top: 0;
  z-index: 100;
  box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}
.app-header h1 {
  font-family: 'M PLUS Rounded 1c', sans-serif;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: 0.02em;
}
.app-header p { font-size: 0.85rem; opacity: 0.85; margin-top: 4px; }

/* Tabs */
.tabs {
  display: flex;
  background: var(--card);
  border-bottom: 2px solid var(--border);
  position: sticky;
  top: 76px;
  z-index: 99;
  box-shadow: var(--shadow);
}
.tab {
  flex: 1;
  padding: 14px 8px;
  text-align: center;
  font-size: 0.9rem;
  font-weight: 500;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  transition: all 0.2s;
  color: var(--text-sub);
}
.tab:hover { background: var(--accent-light); }
.tab.active {
  color: var(--accent);
  border-bottom-color: var(--accent);
  font-weight: 700;
}
.tab-icon { font-size: 1.2rem; display: block; margin-bottom: 2px; }

/* Content */
.content { max-width: 1400px; margin: 0 auto; padding: 24px 16px; }
.panel { display: none; }
.panel.active { display: block; }

/* Cards */
.card {
  background: var(--card);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 24px;
  margin-bottom: 20px;
  border: 1px solid var(--border);
}
.card-title {
  font-family: 'M PLUS Rounded 1c', sans-serif;
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid var(--accent-light);
}

/* Forms */
.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.form-group { display: flex; flex-direction: column; gap: 4px; }
.form-group label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-sub);
}
.form-group input, .form-group select, .form-group textarea {
  padding: 8px 12px;
  border: 1.5px solid var(--border);
  border-radius: 8px;
  font-size: 0.95rem;
  font-family: inherit;
  transition: border-color 0.2s;
  background: #fafafa;
}
.form-group input:focus, .form-group select:focus, .form-group textarea:focus {
  outline: none;
  border-color: var(--accent);
  background: white;
  box-shadow: 0 0 0 3px rgba(59,108,180,0.1);
}
.time-input {
  width: 100%;
  text-align: center;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.5px;
}

/* Lesson cards */
.lesson-card {
  background: var(--card);
  border-radius: var(--radius);
  border: 1.5px solid var(--border);
  padding: 16px;
  margin-bottom: 12px;
  transition: all 0.2s;
  position: relative;
}
.lesson-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.08); }
.lesson-card.eqwel { border-left: 4px solid var(--eqwel); }
.lesson-card.swimming { border-left: 4px solid var(--swimming); }
.lesson-card.piano { border-left: 4px solid var(--piano); }
.lesson-card.other { border-left: 4px solid var(--reviewing); }
.lesson-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}
.lesson-id {
  background: var(--accent);
  color: white;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 0.8rem;
  font-weight: 700;
}
.lesson-name { font-weight: 700; font-size: 1rem; }
.lesson-who {
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 700;
}
.lesson-who.sister { background: var(--sister-bg); color: var(--sister); }
.lesson-who.brother { background: var(--brother-bg); color: var(--brother); }
.lesson-who.both { background: linear-gradient(90deg, var(--sister-bg), var(--brother-bg)); color: #555; }
.lesson-status {
  margin-left: auto;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 700;
}
.lesson-status.confirmed { background: #e8f5e9; color: var(--confirmed); }
.lesson-status.candidate { background: #fff8e1; color: var(--candidate); }
.lesson-status.reviewing { background: #f5f5f5; color: var(--reviewing); }
.delete-btn {
  position: absolute;
  top: 8px;
  right: 8px;
  background: none;
  border: none;
  color: #ccc;
  cursor: pointer;
  font-size: 1.2rem;
  padding: 4px;
  border-radius: 50%;
  transition: all 0.2s;
}
.delete-btn:hover { color: #e74c3c; background: #fde8e8; }

/* Add button */
.add-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 14px;
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  background: none;
  color: var(--text-sub);
  font-size: 0.95rem;
  cursor: pointer;
  transition: all 0.2s;
  font-family: inherit;
}
.add-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-light);
}

/* Lesson table */
.lesson-table-wrap { overflow-x: auto; }
.lesson-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
  min-width: 900px;
}
.lesson-table th {
  background: var(--accent);
  color: white;
  padding: 8px 6px;
  font-weight: 600;
  font-size: 0.75rem;
  white-space: nowrap;
  position: sticky;
  top: 0;
  z-index: 1;
  cursor: pointer;
  user-select: none;
}
.lesson-table th:hover { background: #2d5a9e; }
.lesson-table th .sort-arrow { font-size: 0.6rem; margin-left: 2px; opacity: 0.5; }
.lesson-table th.sorted .sort-arrow { opacity: 1; }
.lesson-table td {
  padding: 4px 4px;
  border-bottom: 1px solid var(--border);
  vertical-align: middle;
}
.lesson-table tr:hover td { background: var(--accent-light); }
.lesson-table input, .lesson-table select {
  width: 100%;
  padding: 5px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.82rem;
  font-family: inherit;
  background: #fafafa;
  box-sizing: border-box;
}
.lesson-table input:focus, .lesson-table select:focus {
  outline: none;
  border-color: var(--accent);
  background: white;
}
.lesson-table .col-id { width: 80px; }
.lesson-table .col-name { min-width: 90px; }
.lesson-table .col-school { min-width: 80px; }
.lesson-table .col-who { width: 100px; }
.lesson-table .col-day { width: 58px; }
.lesson-table .col-time { width: 80px; }
.lesson-table .col-fee { width: 72px; }
.lesson-table .col-status { width: 84px; }
.lesson-table .col-url { min-width: 50px; text-align: center; }
.lesson-table .col-memo { min-width: 120px; }
.lesson-table .memo-cell {
  position: relative;
}
.lesson-table .memo-cell textarea {
  width: 100%;
  padding: 5px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.82rem;
  font-family: inherit;
  background: #fafafa;
  box-sizing: border-box;
  resize: vertical;
  min-height: 30px;
  max-height: 60px;
  line-height: 1.4;
}
.lesson-table .memo-cell textarea:focus {
  outline: none;
  border-color: var(--accent);
  background: white;
  max-height: 200px;
  min-height: 60px;
  z-index: 10;
  position: relative;
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
}
.csv-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1.5px solid var(--accent);
  border-radius: 8px;
  background: white;
  color: var(--accent);
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
}
.csv-btn:hover { background: var(--accent); color: white; }
.lesson-table .col-actions { width: 56px; text-align: center; white-space: nowrap; }
.lesson-table .del-btn,
.lesson-table .copy-btn {
  background: none;
  border: none;
  color: #ccc;
  cursor: pointer;
  font-size: 1rem;
  padding: 2px 6px;
  border-radius: 4px;
}
.lesson-table .del-btn:hover { color: #e74c3c; background: #fde8e8; }
.lesson-table .copy-btn:hover { color: var(--accent); background: var(--accent-light); }
.lesson-table .url-link {
  color: var(--accent);
  text-decoration: none;
  font-size: 0.85rem;
}
.lesson-table .url-link:hover { text-decoration: underline; }
.who-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.72rem;
  font-weight: 700;
  white-space: nowrap;
}
.who-badge.sister { background: var(--sister-bg); color: var(--sister); }
.who-badge.brother { background: var(--brother-bg); color: var(--brother); }
.who-badge.both { background: linear-gradient(90deg, var(--sister-bg), var(--brother-bg)); color: #555; }

/* Calendar-style schedule */
.schedule-wrapper { overflow-x: auto; }
.cal-grid {
  display: grid;
  grid-template-columns: 54px repeat(7, 1fr);
  min-width: 700px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  background: white;
}
.cal-header {
  padding: 10px 4px;
  font-weight: 700;
  text-align: center;
  color: white;
  font-size: 0.85rem;
}
.cal-day-col {
  position: relative;
  border-left: 1px solid var(--border);
}
.cal-time-labels {
  border-right: 1px solid var(--border);
}
.cal-time-label {
  height: 48px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  font-size: 0.7rem;
  color: var(--text-sub);
  font-weight: 500;
  padding-top: 2px;
  border-top: 1px solid #f0eeeb;
  position: relative;
}
.cal-time-label::after {
  content: '';
  position: absolute;
  top: 0;
  right: -1px;
  width: 8px;
  border-top: 1px solid #e0ddd8;
}
.cal-hour-line {
  position: absolute;
  left: 0; right: 0;
  border-top: 1px solid #f0eeeb;
  height: 0;
  pointer-events: none;
}
.cal-event {
  position: absolute;
  left: 3px; right: 3px;
  border-radius: 6px;
  padding: 4px 6px;
  font-size: 0.72rem;
  font-weight: 600;
  line-height: 1.3;
  overflow: hidden;
  z-index: 2;
  display: flex;
  flex-direction: column;
  justify-content: center;
  box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  cursor: default;
  transition: box-shadow 0.15s;
}
.cal-event:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.18); z-index: 3; }
.cal-event.eqwel { background: var(--eqwel-bg); color: var(--eqwel); border-left: 3px solid var(--eqwel); }
.cal-event.swimming { background: var(--swimming-bg); color: var(--swimming); border-left: 3px solid var(--swimming); }
.cal-event.piano { background: var(--piano-bg); color: var(--piano); border-left: 3px solid var(--piano); }
.cal-event.other { background: #f5f5f5; color: #666; border-left: 3px solid #bbb; }
/* Who-based coloring for calendar events */
.cal-event.who-sister { background: var(--sister-bg); color: #c05a20; border-left: 4px solid var(--sister); }
.cal-event.who-brother { background: var(--brother-bg); color: #2a9d8f; border-left: 4px solid var(--brother); }
.cal-event.who-both { background: linear-gradient(135deg, var(--sister-bg) 50%, var(--brother-bg) 50%); color: #555; border-left: 4px solid var(--sister); border-right: 4px solid var(--brother); }
.cal-event-name { font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cal-event-detail { font-size: 0.65rem; opacity: 0.85; }
.cal-event-who {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 0.62rem;
  margin-top: 1px;
}
.who-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.who-dot.sister { background: var(--sister); }
.who-dot.brother { background: var(--brother); }
/* Overlap: shift horizontally */
.cal-event.overlap-1 { right: 52%; }
.cal-event.overlap-2 { left: 52%; }

/* Pattern sub-tabs */
.pattern-tabs {
  display: flex;
  gap: 0;
  margin-bottom: 20px;
  border-radius: var(--radius);
  overflow: hidden;
  border: 2px solid var(--border);
}
.pattern-tab {
  flex: 1;
  padding: 12px 8px;
  text-align: center;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
  background: var(--card);
  color: var(--text-sub);
  transition: all 0.2s;
  font-family: inherit;
  position: relative;
}
.pattern-tab:not(:last-child) { border-right: 1.5px solid var(--border); }
.pattern-tab:hover { background: var(--accent-light); }
.pattern-tab.active-a { background: var(--pattern-a); color: white; }
.pattern-tab.active-b { background: var(--pattern-b); color: white; }
.pattern-tab.active-c { background: var(--pattern-c); color: white; }

/* Pattern comparison */
.patterns-grid {
  /* single pattern shown at a time */
}
.pattern-card {
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  border: 2px solid var(--border);
  background: var(--card);
}
.pattern-header {
  padding: 12px 16px;
  color: white;
  font-weight: 700;
  font-size: 1rem;
  display: flex;
  align-items: center;
  gap: 8px;
}
.pattern-header.a { background: var(--pattern-a); }
.pattern-header.b { background: var(--pattern-b); }
.pattern-header.c { background: var(--pattern-c); }
.pattern-body { padding: 16px; }
.pattern-ids {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 12px;
}
.pattern-chip {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 0.8rem;
  cursor: pointer;
  border: 1.5px solid var(--border);
  background: white;
  transition: all 0.15s;
  font-family: inherit;
}
.pattern-chip:hover { border-color: var(--accent); }
.pattern-chip.selected {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
.pattern-chip.selected.eqwel { background: var(--eqwel); border-color: var(--eqwel); }
.pattern-chip.selected.swimming { background: var(--swimming); border-color: var(--swimming); }
.pattern-chip.selected.piano { background: var(--piano); border-color: var(--piano); }

/* Pattern group accordion */
.pattern-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
}
.pattern-group {
  border: 1.5px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  background: white;
}
.pattern-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  cursor: pointer;
  user-select: none;
  font-weight: 600;
  font-size: 0.9rem;
  transition: background 0.15s;
}
.pattern-group-header:hover { filter: brightness(0.95); }
.pattern-group-header.eqwel { background: var(--eqwel-bg); color: var(--eqwel); border-left: 4px solid var(--eqwel); }
.pattern-group-header.swimming { background: var(--swimming-bg); color: var(--swimming); border-left: 4px solid var(--swimming); }
.pattern-group-header.piano { background: var(--piano-bg); color: var(--piano); border-left: 4px solid var(--piano); }
.pattern-group-header.other { background: #f5f5f5; color: #666; border-left: 4px solid #bbb; }
.collapse-icon { font-size: 0.7rem; width: 14px; text-align: center; flex-shrink: 0; }
.group-label { font-weight: 700; }
.group-count { font-size: 0.75rem; opacity: 0.8; margin-left: auto; }
.group-actions { display: flex; gap: 4px; margin-left: 8px; }
.group-select-btn {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 0.7rem;
  border: 1px solid currentColor;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-family: inherit;
  opacity: 0.7;
  transition: opacity 0.15s;
}
.group-select-btn:hover { opacity: 1; background: rgba(255,255,255,0.5); }
.pattern-group-body { padding: 8px 12px 12px; border-top: 1px solid var(--border); }
.school-subgroup-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: var(--text-sub);
  margin-top: 8px;
  margin-bottom: 4px;
  padding-left: 4px;
  border-left: 3px solid var(--border);
}
.school-subgroup-label:first-child { margin-top: 0; }

@media (max-width: 768px) {
  .pattern-group-header { padding: 8px 10px; font-size: 0.82rem; }
  .group-actions { flex-wrap: wrap; }
  .group-select-btn { font-size: 0.65rem; padding: 2px 6px; }
}

/* Stats */
.stats-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.stat-box {
  text-align: center;
  padding: 8px 14px;
  border-radius: 8px;
  background: #f8f6f3;
  min-width: 80px;
}
.stat-num { font-size: 1.4rem; font-weight: 700; }
.stat-label { font-size: 0.7rem; color: var(--text-sub); }
.stat-num.warn { color: #e74c3c; }

/* Day filter buttons */
.day-filter {
  display: flex;
  gap: 4px;
  margin-bottom: 12px;
  align-items: center;
}
.day-filter-label {
  font-size: 0.8rem;
  color: var(--text-sub);
  margin-right: 4px;
  white-space: nowrap;
}
.day-filter-btn {
  padding: 6px 14px;
  border-radius: 20px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  border: 2px solid var(--border);
  background: white;
  color: var(--text-sub);
  transition: all 0.15s;
  font-family: inherit;
}
.day-filter-btn:hover { border-color: var(--accent); color: var(--accent); }
.day-filter-btn.active {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}
.day-filter-btn.sat.active { background: #3b7dd8; border-color: #3b7dd8; }
.day-filter-btn.sun.active { background: #d95050; border-color: #d95050; }
.day-filter-reset {
  padding: 4px 10px;
  border-radius: 14px;
  font-size: 0.72rem;
  cursor: pointer;
  border: 1px solid var(--border);
  background: #f5f5f5;
  color: var(--text-sub);
  font-family: inherit;
  margin-left: 4px;
}
.day-filter-reset:hover { background: var(--accent-light); color: var(--accent); }

/* Day count bar */
.day-counts {
  display: flex;
  gap: 4px;
  margin-top: 10px;
}
.day-count-item {
  flex: 1;
  text-align: center;
  padding: 6px 2px;
  border-radius: 6px;
  font-size: 0.75rem;
}
.day-count-item .count { font-weight: 700; font-size: 1.1rem; display: block; }
.day-count-item.has-items { background: var(--accent-light); }
.day-count-item.overload { background: #fde8e8; color: #e74c3c; }

/* Person filter */
.person-filter {
  display: flex;
  gap: 0;
  margin-bottom: 16px;
  border-radius: var(--radius);
  overflow: hidden;
  border: 2px solid var(--border);
}
.person-filter-btn {
  flex: 1;
  padding: 10px 8px;
  text-align: center;
  font-size: 0.88rem;
  font-weight: 600;
  cursor: pointer;
  border: none;
  background: var(--card);
  color: var(--text-sub);
  transition: all 0.2s;
  font-family: inherit;
}
.person-filter-btn:not(:last-child) { border-right: 1.5px solid var(--border); }
.person-filter-btn:hover { background: var(--accent-light); }
.person-filter-btn.active-all { background: var(--accent); color: white; }
.person-filter-btn.active-sister { background: var(--sister); color: white; }
.person-filter-btn.active-brother { background: var(--brother); color: white; }
.person-filter-btn .person-count {
  font-size: 0.72rem;
  opacity: 0.85;
  display: block;
}

@media (max-width: 768px) {
  .app-header { padding: 16px; }
  .app-header h1 { font-size: 1.2rem; }
  .tab { padding: 10px 4px; font-size: 0.78rem; }
  .content { padding: 12px 8px; }
  .pattern-tab { padding: 10px 4px; font-size: 0.8rem; }
  .form-grid { grid-template-columns: 1fr 1fr; }
}
</style>
</head>
<body>

<div class="app-header">
  <h1>🏠 家族スケジュール計画 2026年度</h1>
  <p>習い事の候補を入力 → パターンを組み合わせ → スケジュール表で比較</p>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('lessons')">
    <span class="tab-icon">📝</span>習い事候補
  </div>
  <div class="tab" onclick="showTab('patterns')">
    <span class="tab-icon">📅</span>パターン比較
  </div>
  <div class="tab" onclick="showTab('info')">
    <span class="tab-icon">🏠</span>基本情報
  </div>
</div>

<div class="content">

  <!-- Tab 1: 習い事候補 -->
  <div id="panel-lessons" class="panel active">
    <div class="card">
      <div class="card-title">📝 習い事の候補一覧</div>
      <p style="color:var(--text-sub);font-size:0.85rem;margin-bottom:12px;">
        同じ習い事でも曜日や教室が違う選択肢は、別々に登録してください
      </p>
      <div class="person-filter" id="person-filter"></div>
      <div class="lesson-table-wrap">
        <table class="lesson-table" id="lessons-table"></table>
      </div>
      <div style="display:flex;gap:12px;margin-top:12px;align-items:center;flex-wrap:wrap;">
        <button class="add-btn" style="flex:1;margin:0;" onclick="addLesson()">＋ 習い事候補を追加</button>
        <button class="csv-btn" onclick="renumberAllIds()">🔄 ID振り直し</button>
        <button class="csv-btn" onclick="exportCSV()">📥 CSV出力</button>
      </div>
    </div>
  </div>

  <!-- Tab 2: パターン比較 -->
  <div id="panel-patterns" class="panel">
    <div class="card" style="background:transparent;border:none;box-shadow:none;padding:0;">
      <p style="color:var(--text-sub);font-size:0.85rem;margin-bottom:16px;">
        💡 各パターンで採用したい習い事をクリックして選択 → スケジュール表と集計が自動更新されます
      </p>
      <div class="pattern-tabs" id="pattern-tabs"></div>
      <div class="patterns-grid" id="patterns-grid"></div>
    </div>
  </div>

  <!-- Tab 3: 基本情報 -->
  <div id="panel-info" class="panel">
    <div class="card">
      <div class="card-title">👨‍👩‍👧‍👦 家族メンバー</div>
      <div style="display:grid;gap:16px;" id="family-list"></div>
    </div>
    <div class="card">
      <div class="card-title">📋 前提条件</div>
      <div class="form-grid">
        <div class="form-group">
          <label>月謝の予算上限（円/月）</label>
          <input type="text" id="cond-budget" placeholder="例: 50000" onchange="saveConditions()">
        </div>
        <div class="form-group">
          <label>送迎の許容範囲</label>
          <input type="text" id="cond-travel" placeholder="例: 車15分" onchange="saveConditions()">
        </div>
        <div class="form-group">
          <label>保育園お迎え時間</label>
          <input type="text" id="cond-pickup" class="time-input" inputmode="numeric" placeholder="18:00">
        </div>
        <div class="form-group">
          <label>平日に習い事できる時間帯</label>
          <input type="text" id="cond-weekday" placeholder="例: 16:00〜19:00" onchange="saveConditions()">
        </div>
        <div class="form-group">
          <label>土日に習い事できる時間帯</label>
          <input type="text" id="cond-weekend" placeholder="例: 9:00〜17:00" onchange="saveConditions()">
        </div>
        <div class="form-group">
          <label>パパが送迎可能な曜日</label>
          <input type="text" id="cond-papa" placeholder="例: 土日のみ" onchange="saveConditions()">
        </div>
      </div>
    </div>
  </div>

</div>

<script>
let appData = {{ data_json | safe }};

const DAYS = ['月','火','水','木','金','土','日'];

// =========== Custom Time Input ===========
function parseTimeInput(raw) {
  if (!raw) return '';
  const s = raw.replace(/[^0-9]/g, '');
  if (!s) return '';
  let h, m;
  if (s.length <= 2) {
    h = parseInt(s, 10);
    m = 0;
  } else if (s.length === 3) {
    h = parseInt(s[0], 10);
    m = parseInt(s.slice(1), 10);
  } else {
    h = parseInt(s.slice(0, s.length - 2), 10);
    m = parseInt(s.slice(-2), 10);
  }
  if (isNaN(h) || isNaN(m)) return '';
  h = Math.max(0, Math.min(23, h));
  m = Math.max(0, Math.min(59, m));
  return String(h).padStart(2,'0') + ':' + String(m).padStart(2,'0');
}

function timeToMin(t) {
  if (!t) return -1;
  const p = t.split(':');
  return parseInt(p[0]) * 60 + parseInt(p[1] || 0);
}

function minToTime(m) {
  m = Math.max(0, Math.min(23*60+59, m));
  return String(Math.floor(m/60)).padStart(2,'0') + ':' + String(m%60).padStart(2,'0');
}

function setupTimeInput(input, onChange) {
  input.addEventListener('focus', function() {
    setTimeout(() => this.select(), 0);
  });
  input.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
      e.preventDefault();
      const cur = timeToMin(parseTimeInput(this.value));
      const step = e.key === 'ArrowUp' ? 5 : -5;
      const next = cur < 0 ? (e.key === 'ArrowUp' ? 540 : 540) : cur + step;
      const formatted = minToTime(next);
      this.value = formatted;
      if (onChange) onChange(formatted);
    }
  });
  input.addEventListener('blur', function() {
    const formatted = parseTimeInput(this.value);
    if (formatted && formatted !== this.value) {
      this.value = formatted;
    }
    if (onChange) onChange(formatted);
  });
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      this.blur();
    }
  });
}

function showTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  event.currentTarget.classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
  if (name === 'patterns') renderPatterns();
}

function getLessonClass(name) {
  if (!name) return 'other';
  const n = name.toLowerCase();
  if (n.includes('幼児教室') || n.includes('いくうぇる') || n.includes('eqwel')) return 'eqwel';
  if (n.includes('スイミング') || n.includes('水泳') || n.includes('swim')) return 'swimming';
  if (n.includes('ピアノ') || n.includes('piano')) return 'piano';
  return 'other';
}

// =========== ID Auto-Generation ===========
const CATEGORY_MAP = [
  { pattern: '幼児教室', letter: 'A' },
  { pattern: 'スイミング', letter: 'B' },
  { pattern: '水泳',       letter: 'B' },
  { pattern: 'ピアノ',     letter: 'C' },
];

function getCategoryLetter(lessonName) {
  if (!lessonName) return 'Z';
  for (const entry of CATEGORY_MAP) {
    if (lessonName.includes(entry.pattern)) return entry.letter;
  }
  // Dynamic assignment for unknown categories: D, E, F, ...
  const usedLetters = new Set(CATEGORY_MAP.map(e => e.letter));
  const unknownNames = [];
  appData.lessons.forEach(l => {
    if (!l.name) return;
    const matched = CATEGORY_MAP.some(e => l.name.includes(e.pattern));
    if (!matched) {
      const base = l.name.split(/[（(]/)[0];
      if (!unknownNames.includes(base)) unknownNames.push(base);
    }
  });
  const baseName = lessonName.split(/[（(]/)[0];
  let idx = unknownNames.indexOf(baseName);
  if (idx < 0) { unknownNames.push(baseName); idx = unknownNames.length - 1; }
  let letter = 'D';
  let assigned = 0;
  while (assigned <= idx) {
    if (!usedLetters.has(letter)) {
      if (assigned === idx) return letter;
      assigned++;
    }
    letter = String.fromCharCode(letter.charCodeAt(0) + 1);
  }
  return 'Z';
}

function generateLessonId(who, lessonName, excludeIdx) {
  const personPrefix = who || '_';
  const catLetter = getCategoryLetter(lessonName);
  let maxNum = 0;
  appData.lessons.forEach((l, i) => {
    if (i === excludeIdx || !l.id) return;
    const match = l.id.match(/^(.+)-([A-Z])(\d+)$/);
    if (match && match[1] === personPrefix && match[2] === catLetter) {
      maxNum = Math.max(maxNum, parseInt(match[3]));
    }
  });
  return personPrefix + '-' + catLetter + String(maxNum + 1).padStart(2, '0');
}

function isAutoGeneratedId(id) {
  return /^.+-[A-Z]\d+$/.test(id);
}

function updatePatternIds(oldId, newId) {
  if (!oldId || oldId === newId) return;
  ['A', 'B', 'C'].forEach(patKey => {
    const ids = appData.patterns[patKey].ids;
    const idx = ids.indexOf(oldId);
    if (idx >= 0) {
      if (newId) ids[idx] = newId;
      else ids.splice(idx, 1);
    }
  });
}

function naturalCompare(a, b) {
  const re = /(\d+)|(\D+)/g;
  const aParts = String(a).match(re) || [];
  const bParts = String(b).match(re) || [];
  const len = Math.min(aParts.length, bParts.length);
  for (let i = 0; i < len; i++) {
    const aIsNum = /^\d+$/.test(aParts[i]);
    const bIsNum = /^\d+$/.test(bParts[i]);
    if (aIsNum && bIsNum) {
      const diff = parseInt(aParts[i]) - parseInt(bParts[i]);
      if (diff !== 0) return diff;
    } else {
      const cmp = aParts[i].localeCompare(bParts[i], 'ja');
      if (cmp !== 0) return cmp;
    }
  }
  return aParts.length - bParts.length;
}

function getStatusClass(s) {
  if (!s) return 'reviewing';
  if (s.includes('確定')) return 'confirmed';
  if (s.includes('候補')) return 'candidate';
  return 'reviewing';
}

function getWhoClass(w) {
  if (!w) return '';
  const f = appData.family;
  const sisterName = f.sister ? f.sister.name : 'お姉ちゃん';
  const brotherName = f.brother ? f.brother.name : '弟くん';
  const bothName = sisterName + '＋' + brotherName;
  if (w === bothName) return 'both';
  if (w === sisterName) return 'sister';
  if (w === brotherName) return 'brother';
  // fallback for legacy data
  if (w.includes('＋')) return 'both';
  if (w.includes('姉') && !w.includes('弟')) return 'sister';
  if (w.includes('弟') && !w.includes('姉')) return 'brother';
  return 'sister';
}

function getWhoEmoji(w) {
  const f = appData.family;
  const sisterName = f.sister ? f.sister.name : 'お姉ちゃん';
  const brotherName = f.brother ? f.brother.name : '弟くん';
  const bothName = sisterName + '＋' + brotherName;
  if (w === sisterName) return '👧';
  if (w === brotherName) return '👶';
  if (w === bothName) return '👧👶';
  return '';
}

function escHtml(str) {
  if (!str) return '';
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/`/g,'&#96;').replace(/\$/g,'&#36;');
}

function urlLink(url) {
  if (!url) return '';
  var safe = escHtml(url);
  return '<a class="url-link" href="' + safe + '" target="_blank" rel="noopener" title="' + safe + '">🔗</a>';
}

function buildWhoOptions(current) {
  const f = appData.family;
  const sisterName = f.sister ? f.sister.name : 'お姉ちゃん';
  const brotherName = f.brother ? f.brother.name : '弟くん';
  const bothName = sisterName + '＋' + brotherName;
  const options = [sisterName, brotherName, bothName];
  return options.map(o => `<option value="${o}" ${current===o?'selected':''}>${o}</option>`).join('');
}

// =========== Person Filter ===========
let lessonPersonFilter = 'all'; // 'all', 'sister', 'brother'

function setPersonFilter(filter) {
  lessonPersonFilter = filter;
  renderPersonFilter();
  renderLessons();
}

function renderPersonFilter() {
  const container = document.getElementById('person-filter');
  const f = appData.family;
  const sisterName = f.sister ? f.sister.name : 'お姉ちゃん';
  const brotherName = f.brother ? f.brother.name : '弟くん';

  const sisterCount = appData.lessons.filter(l => l.who === sisterName || (l.who && l.who.includes(sisterName))).length;
  const brotherCount = appData.lessons.filter(l => l.who === brotherName || (l.who && l.who.includes(brotherName))).length;
  const allCount = appData.lessons.length;

  container.innerHTML = `
    <button class="person-filter-btn${lessonPersonFilter==='all'?' active-all':''}" onclick="setPersonFilter('all')">
      📋 全員<span class="person-count">${allCount}件</span>
    </button>
    <button class="person-filter-btn${lessonPersonFilter==='sister'?' active-sister':''}" onclick="setPersonFilter('sister')">
      👧 ${sisterName}<span class="person-count">${sisterCount}件</span>
    </button>
    <button class="person-filter-btn${lessonPersonFilter==='brother'?' active-brother':''}" onclick="setPersonFilter('brother')">
      👶 ${brotherName}<span class="person-count">${brotherCount}件</span>
    </button>
  `;
}

function getFilteredLessonIndices(sortedIndices) {
  if (lessonPersonFilter === 'all') return sortedIndices;
  const f = appData.family;
  const filterName = lessonPersonFilter === 'sister'
    ? (f.sister ? f.sister.name : 'お姉ちゃん')
    : (f.brother ? f.brother.name : '弟くん');
  return sortedIndices.filter(idx => {
    const who = appData.lessons[idx].who || '';
    return who === filterName || who.includes(filterName);
  });
}

// =========== Lessons ===========
let lessonSort = { key: null, asc: true };

function sortLessons(key) {
  if (lessonSort.key === key) {
    lessonSort.asc = !lessonSort.asc;
  } else {
    lessonSort.key = key;
    lessonSort.asc = true;
  }
  renderLessons();
}

function getSortedLessonIndices() {
  const indices = appData.lessons.map((_, i) => i);
  if (!lessonSort.key) return indices;
  const k = lessonSort.key;
  const dayOrder = {'月':0,'火':1,'水':2,'木':3,'金':4,'土':5,'日':6};
  indices.sort((a, b) => {
    let va = appData.lessons[a][k] || '';
    let vb = appData.lessons[b][k] || '';
    if (k === 'fee') {
      va = parseInt(va) || 0;
      vb = parseInt(vb) || 0;
      return lessonSort.asc ? va - vb : vb - va;
    }
    if (k === 'day') {
      va = dayOrder[va] !== undefined ? dayOrder[va] : 99;
      vb = dayOrder[vb] !== undefined ? dayOrder[vb] : 99;
      return lessonSort.asc ? va - vb : vb - va;
    }
    va = String(va);
    vb = String(vb);
    const cmp = k === 'id' ? naturalCompare(va, vb) : va.localeCompare(vb, 'ja');
    return lessonSort.asc ? cmp : -cmp;
  });
  return indices;
}

function renderLessons() {
  const table = document.getElementById('lessons-table');
  const cols = [
    {key:'id', label:'ID', cls:'col-id'},
    {key:'name', label:'習い事', cls:'col-name'},
    {key:'school', label:'教室', cls:'col-school'},
    {key:'who', label:'対象', cls:'col-who'},
    {key:'day', label:'曜日', cls:'col-day'},
    {key:'start', label:'開始', cls:'col-time'},
    {key:'end', label:'終了', cls:'col-time'},
    {key:'fee', label:'月謝', cls:'col-fee'},
    {key:'status', label:'状態', cls:'col-status'},
    {key:null, label:'URL', cls:'col-url'},
    {key:'memo', label:'備考', cls:'col-memo'},
    {key:null, label:'', cls:'col-actions'},
  ];
  let html = '<thead><tr>';
  cols.forEach(c => {
    if (c.key) {
      const sorted = lessonSort.key === c.key;
      const arrow = sorted ? (lessonSort.asc ? '▲' : '▼') : '▲';
      html += `<th class="${c.cls}${sorted?' sorted':''}" onclick="sortLessons('${c.key}')">${c.label}<span class="sort-arrow">${arrow}</span></th>`;
    } else {
      html += `<th class="${c.cls}">${c.label}</th>`;
    }
  });
  html += '</tr></thead><tbody>';

  const sortedIndices = getSortedLessonIndices();
  const filteredIndices = getFilteredLessonIndices(sortedIndices);
  filteredIndices.forEach(idx => {
    const lesson = appData.lessons[idx];
    html += `<tr>
      <td><input value="${escHtml(lesson.id)}" onchange="updateLesson(${idx},'id',this.value)" placeholder="自動" style="font-weight:700;color:var(--accent);font-size:0.82rem;" title="対象と習い事名から自動生成。手動入力で上書き可能。"></td>
      <td><input value="${escHtml(lesson.name)}" onchange="updateLesson(${idx},'name',this.value)" placeholder="幼児教室"></td>
      <td><input value="${escHtml(lesson.school)}" onchange="updateLesson(${idx},'school',this.value)" placeholder="○○教室"></td>
      <td><select onchange="updateLesson(${idx},'who',this.value)">
            <option value="">-</option>
            ${buildWhoOptions(lesson.who)}
          </select></td>
      <td><select onchange="updateLesson(${idx},'day',this.value)">
            <option value="">-</option>
            ${DAYS.map(d => '<option value="' + d + '"' + (lesson.day===d?' selected':'') + '>' + d + '</option>').join('')}
          </select></td>
      <td><input type="text" class="time-input" data-time-field="start" data-lesson-idx="${idx}" value="${lesson.start || ''}" inputmode="numeric" placeholder="9:00"></td>
      <td><input type="text" class="time-input" data-time-field="end" data-lesson-idx="${idx}" value="${lesson.end || ''}" inputmode="numeric" placeholder="10:00"></td>
      <td><input type="number" value="${lesson.fee || ''}" onchange="updateLesson(${idx},'fee',this.value)" placeholder="7000" style="width:70px"></td>
      <td><select onchange="updateLesson(${idx},'status',this.value)">
            <option value="継続確定" ${lesson.status==='継続確定'?'selected':''}>継続確定</option>
            <option value="新規確定" ${lesson.status==='新規確定'?'selected':''}>新規確定</option>
            <option value="第1候補" ${lesson.status==='第1候補'?'selected':''}>第1候補</option>
            <option value="第2候補" ${lesson.status==='第2候補'?'selected':''}>第2候補</option>
            <option value="検討中" ${lesson.status==='検討中'?'selected':''}>検討中</option>
          </select></td>
      <td><div style="display:flex;align-items:center;gap:4px"><input type="url" value="${escHtml(lesson.url)}" onchange="updateLesson(${idx},'url',this.value)" placeholder="https://..." style="flex:1;min-width:60px">${urlLink(lesson.url)}</div></td>
      <td class="memo-cell"><textarea data-idx="${idx}" placeholder="メモ"></textarea></td>
      <td><button class="copy-btn" onclick="duplicateLesson(${idx})" title="複製">📋</button><button class="del-btn" onclick="deleteLesson(${idx})" title="削除">✕</button></td>
    </tr>`;
  });

  html += '</tbody>';
  table.innerHTML = html;

  // Set memo values via DOM to avoid template literal issues with special characters
  table.querySelectorAll('textarea[data-idx]').forEach(ta => {
    const i = parseInt(ta.getAttribute('data-idx'));
    ta.value = appData.lessons[i].memo || '';
    ta.onchange = function() { updateLesson(i, 'memo', this.value); };
  });

  // Setup custom time inputs
  table.querySelectorAll('.time-input').forEach(inp => {
    const idx = parseInt(inp.dataset.lessonIdx);
    const field = inp.dataset.timeField;
    setupTimeInput(inp, (val) => updateLesson(idx, field, val));
  });
}

function updateLesson(idx, field, value) {
  const lesson = appData.lessons[idx];
  const oldId = lesson.id;
  lesson[field] = value;

  // Auto-generate ID when 'who' or 'name' changes
  if (field === 'who' || field === 'name') {
    if (lesson.who && lesson.name) {
      const newId = generateLessonId(lesson.who, lesson.name, idx);
      if (!oldId || isAutoGeneratedId(oldId)) {
        lesson.id = newId;
        updatePatternIds(oldId, newId);
      }
    }
  }
  // If user manually edits the ID field, update pattern references
  if (field === 'id' && oldId !== value) {
    updatePatternIds(oldId, value);
  }

  saveToServer();
  if (field === 'who') renderPersonFilter();
  renderLessons();
}

function addLesson() {
  const f = appData.family;
  let defaultWho = '';
  if (lessonPersonFilter === 'sister') {
    defaultWho = f.sister ? f.sister.name : 'お姉ちゃん';
  } else if (lessonPersonFilter === 'brother') {
    defaultWho = f.brother ? f.brother.name : '弟くん';
  }
  appData.lessons.push({
    id: '', name: '', school: '', address: '', who: defaultWho, day: '', start: '', end: '', fee: '', status: '検討中', url: '', memo: ''
  });
  saveToServer();
  renderPersonFilter();
  renderLessons();
}

function deleteLesson(idx) {
  if (confirm('この候補を削除しますか？')) {
    const deletedId = appData.lessons[idx].id;
    appData.lessons.splice(idx, 1);
    if (deletedId) {
      ['A', 'B', 'C'].forEach(patKey => {
        const ids = appData.patterns[patKey].ids;
        const pidx = ids.indexOf(deletedId);
        if (pidx >= 0) ids.splice(pidx, 1);
      });
    }
    saveToServer();
    renderPersonFilter();
    renderLessons();
  }
}

function duplicateLesson(idx) {
  const src = appData.lessons[idx];
  const copy = Object.assign({}, src);
  copy.id = '';
  // Auto-generate new ID if possible
  if (copy.who && copy.name) {
    copy.id = generateLessonId(copy.who, copy.name, -1);
  }
  appData.lessons.splice(idx + 1, 0, copy);
  saveToServer();
  renderPersonFilter();
  renderLessons();
}

function renumberAllIds() {
  if (!confirm('全てのIDを自動で振り直しますか？\\n（パターンの参照も自動更新されます）')) return;
  const idMap = {};
  const counters = {};
  appData.lessons.forEach(lesson => {
    const oldId = lesson.id;
    const person = lesson.who || '_';
    const catLetter = getCategoryLetter(lesson.name);
    const key = person + '-' + catLetter;
    counters[key] = (counters[key] || 0) + 1;
    const newId = person + '-' + catLetter + String(counters[key]).padStart(2, '0');
    if (oldId && oldId !== newId) idMap[oldId] = newId;
    lesson.id = newId;
  });
  ['A', 'B', 'C'].forEach(patKey => {
    appData.patterns[patKey].ids = appData.patterns[patKey].ids.map(oldId => idMap[oldId] || oldId);
  });
  saveToServer();
  renderPersonFilter();
  renderLessons();
}

// =========== CSV Export ===========
function exportCSV() {
  const BOM = '\uFEFF';
  const headers = ['ID','習い事','教室','対象','曜日','開始','終了','月謝','状態','URL','備考'];
  const rows = [headers.join(',')];
  const sortedIndices = getSortedLessonIndices();
  const filteredIndices = getFilteredLessonIndices(sortedIndices);
  filteredIndices.forEach(idx => {
    const l = appData.lessons[idx];
    const fields = [l.id, l.name, l.school, l.who, l.day, l.start, l.end, l.fee, l.status, l.url, l.memo];
    rows.push(fields.map(v => {
      const s = String(v || '').replace(/"/g, '""');
      return s.includes(',') || s.includes('"') || s.includes(String.fromCharCode(10)) ? '"' + s + '"' : s;
    }).join(','));
  });
  const blob = new Blob([BOM + rows.join(String.fromCharCode(10))], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = '習い事候補_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// =========== Patterns ===========
let activePatternTab = 'A';
let patternDayFilter = ['月','火','水','木','金','土','日'];
let patternPersonFilter = 'all';
let patternCollapsedGroups = new Set();

function switchPatternTab(key) {
  activePatternTab = key;
  renderPatterns();
}

function toggleDayFilter(day) {
  const idx = patternDayFilter.indexOf(day);
  if (idx >= 0) {
    if (patternDayFilter.length === 1) return; // keep at least 1 day
    patternDayFilter.splice(idx, 1);
  } else {
    patternDayFilter.push(day);
    // restore DAYS order
    patternDayFilter.sort((a, b) => DAYS.indexOf(a) - DAYS.indexOf(b));
  }
  renderPatterns();
}

function resetDayFilter() {
  patternDayFilter = ['月','火','水','木','金','土','日'];
  renderPatterns();
}

function setPatternPersonFilter(filter) {
  patternPersonFilter = filter;
  renderPatterns();
}

function toggleGroupCollapse(catKey) {
  if (patternCollapsedGroups.has(catKey)) {
    patternCollapsedGroups.delete(catKey);
  } else {
    patternCollapsedGroups.add(catKey);
  }
  renderPatterns();
}

function selectAllInGroup(patKey, catKey, selectAll) {
  const ids = appData.patterns[patKey].ids;
  const f = appData.family;
  const sisterName = f.sister ? f.sister.name : 'お姉ちゃん';
  const brotherName = f.brother ? f.brother.name : '弟くん';

  appData.lessons.filter(l => l.id).forEach(lesson => {
    if (getCategoryLetter(lesson.name) !== catKey) return;
    if (patternPersonFilter !== 'all') {
      const filterName = patternPersonFilter === 'sister' ? sisterName : brotherName;
      if (lesson.who !== filterName && !(lesson.who && lesson.who.includes(filterName))) return;
    }
    if (lesson.day && !patternDayFilter.includes(lesson.day)) return;
    const idx = ids.indexOf(lesson.id);
    if (selectAll && idx < 0) {
      ids.push(lesson.id);
    } else if (!selectAll && idx >= 0) {
      ids.splice(idx, 1);
    }
  });
  saveToServer();
  renderPatterns();
}

function renderPatterns() {
  const tabsContainer = document.getElementById('pattern-tabs');
  const grid = document.getElementById('patterns-grid');

  const patKeys = ['A','B','C'];
  const patColors = { A:'a', B:'b', C:'c' };

  // Render sub-tabs
  let tabsHtml = '';
  patKeys.forEach(key => {
    const pat = appData.patterns[key];
    const stats = calcStats(pat.ids || []);
    const isActive = key === activePatternTab;
    const activeCls = isActive ? ` active-${patColors[key]}` : '';
    tabsHtml += `<button class="pattern-tab${activeCls}" onclick="switchPatternTab('${key}')">
      ${pat.name || 'パターン'+key}
      <span style="font-size:0.75rem;opacity:0.85;display:block;">${stats.total}件 / ${stats.fee ? stats.fee.toLocaleString()+'円' : '-'}</span>
    </button>`;
  });
  tabsContainer.innerHTML = tabsHtml;

  // Render active pattern only
  grid.innerHTML = '';
  const key = activePatternTab;
  const pi = patColors[key];
  const pat = appData.patterns[key];
  const selectedIds = pat.ids || [];
  const stats = calcStats(selectedIds);

  let html = `
    <div class="pattern-card">
      <div class="pattern-header ${pi}">
        📋 ${pat.name || 'パターン'+key}
      </div>
      <div class="pattern-body">
        <div style="font-size:0.8rem;color:var(--text-sub);margin-bottom:8px;">採用する候補をクリック：</div>`;

  // Person filter for pattern tab
  const f = appData.family;
  const sisterName = f.sister ? f.sister.name : 'お姉ちゃん';
  const brotherName = f.brother ? f.brother.name : '弟くん';
  const lessonsWithId = appData.lessons.filter(l => l.id);
  const allCount = lessonsWithId.length;
  const sisterCount = lessonsWithId.filter(l => l.who === sisterName || (l.who && l.who.includes(sisterName))).length;
  const brotherCount = lessonsWithId.filter(l => l.who === brotherName || (l.who && l.who.includes(brotherName))).length;

  html += `<div class="person-filter" style="margin-bottom:8px;">
    <button class="person-filter-btn${patternPersonFilter==='all'?' active-all':''}" onclick="setPatternPersonFilter('all')">
      📋 全員<span class="person-count">${allCount}件</span>
    </button>
    <button class="person-filter-btn${patternPersonFilter==='sister'?' active-sister':''}" onclick="setPatternPersonFilter('sister')">
      👧 ${sisterName}<span class="person-count">${sisterCount}件</span>
    </button>
    <button class="person-filter-btn${patternPersonFilter==='brother'?' active-brother':''}" onclick="setPatternPersonFilter('brother')">
      👶 ${brotherName}<span class="person-count">${brotherCount}件</span>
    </button>
  </div>`;

  // Day filter buttons (above chips for filtering)
  const filteredDays = DAYS.filter(d => patternDayFilter.includes(d));
  const isAllDays = filteredDays.length === 7;
  html += `<div class="day-filter" style="margin-bottom:10px;">`;
  html += `<span class="day-filter-label">曜日絞込:</span>`;
  DAYS.forEach(d => {
    const isActive = patternDayFilter.includes(d);
    const dayCls = d === '土' ? ' sat' : d === '日' ? ' sun' : '';
    html += `<button class="day-filter-btn${dayCls}${isActive?' active':''}" onclick="toggleDayFilter('${d}')">${d}</button>`;
  });
  if (!isAllDays) {
    html += `<button class="day-filter-reset" onclick="resetDayFilter()">全曜日表示</button>`;
  }
  html += `</div>`;

  // Filter lessons by person and day
  let filteredLessons = lessonsWithId.slice();
  if (patternPersonFilter !== 'all') {
    const filterName = patternPersonFilter === 'sister' ? sisterName : brotherName;
    filteredLessons = filteredLessons.filter(l => l.who === filterName || (l.who && l.who.includes(filterName)));
  }
  filteredLessons = filteredLessons.filter(l => !l.day || patternDayFilter.includes(l.day));
  filteredLessons.sort((a, b) => naturalCompare(a.id, b.id));

  // Group by category, then by school
  const CATEGORY_LABELS = { A: '幼児教室', B: 'スイミング', C: 'ピアノ' };
  const groups = {};
  filteredLessons.forEach(lesson => {
    const catLetter = getCategoryLetter(lesson.name);
    if (!groups[catLetter]) {
      const baseName = lesson.name.split(/[（(]/)[0].trim();
      groups[catLetter] = {
        label: CATEGORY_LABELS[catLetter] || baseName,
        cssClass: getLessonClass(lesson.name),
        schools: {},
        count: 0,
        selectedCount: 0
      };
    }
    const school = lesson.school || '（教室未設定）';
    if (!groups[catLetter].schools[school]) {
      groups[catLetter].schools[school] = [];
    }
    groups[catLetter].schools[school].push(lesson);
    groups[catLetter].count++;
    if (selectedIds.includes(lesson.id)) groups[catLetter].selectedCount++;
  });

  // Render grouped chips
  const sortedCatKeys = Object.keys(groups).sort();
  html += `<div class="pattern-groups">`;

  if (sortedCatKeys.length === 0) {
    html += `<div style="color:var(--text-sub);font-size:0.85rem;padding:12px;">該当する候補がありません</div>`;
  }

  sortedCatKeys.forEach(catKey => {
    const group = groups[catKey];
    const isCollapsed = patternCollapsedGroups.has(catKey);

    html += `<div class="pattern-group">`;
    html += `<div class="pattern-group-header ${group.cssClass}" onclick="toggleGroupCollapse('${catKey}')">
      <span class="collapse-icon">${isCollapsed ? '▶' : '▼'}</span>
      <span class="group-label">${group.label}</span>
      <span class="group-count">${group.selectedCount}/${group.count}件選択</span>
      <span class="group-actions">
        <button class="group-select-btn" onclick="event.stopPropagation();selectAllInGroup('${key}','${catKey}',true)">全選択</button>
        <button class="group-select-btn" onclick="event.stopPropagation();selectAllInGroup('${key}','${catKey}',false)">全解除</button>
      </span>
    </div>`;

    if (!isCollapsed) {
      html += `<div class="pattern-group-body">`;
      const schoolNames = Object.keys(group.schools).sort();

      schoolNames.forEach(school => {
        if (schoolNames.length > 1) {
          html += `<div class="school-subgroup-label">${school}</div>`;
        }
        html += `<div class="pattern-ids">`;
        group.schools[school].forEach(lesson => {
          const isSelected = selectedIds.includes(lesson.id);
          const cls = getLessonClass(lesson.name);
          const whoMark = getWhoEmoji(lesson.who);
          const dayLabel = lesson.day || '';
          const timeLabel = lesson.start || '';
          // Extract variant from name (e.g., ベビー, リトル, キンダー)
          const variantMatch = lesson.name.match(/[（(]([^）)]+)[）)]/);
          const variant = variantMatch ? variantMatch[1] : '';
          const chipLabel = [dayLabel, timeLabel, variant].filter(Boolean).join(' ');
          html += `<button class="pattern-chip ${isSelected ? 'selected '+cls : ''}"
                    onclick="togglePatternId('${key}','${escHtml(lesson.id)}')">
                    ${chipLabel || lesson.name} ${whoMark}
                   </button>`;
        });
        html += `</div>`;
      });

      html += `</div>`;
    }
    html += `</div>`;
  });

  html += `</div>`;

  // Calendar-style schedule (full day view)
  const PX_PER_HOUR = 64;
  const minH = 7;
  const maxH = 22;
  const dispHours = maxH - minH;
  const gridH = dispHours * PX_PER_HOUR;
  const numDays = filteredDays.length;

  html += `<div class="schedule-wrapper"><div class="cal-grid" style="grid-template-columns:54px repeat(${numDays}, 1fr);grid-template-rows:auto ${gridH}px;min-width:${Math.max(200, numDays * 100 + 54)}px">`;

  html += `<div class="cal-header" style="background:var(--pattern-${pi})"></div>`;
  filteredDays.forEach(d => {
    html += `<div class="cal-header" style="background:var(--pattern-${pi})">${d}</div>`;
  });

  html += `<div class="cal-time-labels" style="position:relative;">`;
  for (let h = minH; h < maxH; h++) {
    const top = (h - minH) * PX_PER_HOUR;
    html += `<div class="cal-time-label" style="position:absolute;top:${top}px;left:0;right:0;height:${PX_PER_HOUR}px;">${h}:00</div>`;
  }
  html += `</div>`;

  filteredDays.forEach(d => {
    html += `<div class="cal-day-col" style="position:relative;height:${gridH}px;">`;

    for (let h = minH; h < maxH; h++) {
      const top = (h - minH) * PX_PER_HOUR;
      html += `<div class="cal-hour-line" style="top:${top}px;"></div>`;
    }

    const dayEvents = [];
    selectedIds.forEach(id => {
      const lesson = appData.lessons.find(l => l.id === id);
      if (!lesson || lesson.day !== d || !lesson.start || !lesson.end) return;
      const sParts = lesson.start.split(':');
      const eParts = lesson.end.split(':');
      const startMin = parseInt(sParts[0]) * 60 + parseInt(sParts[1] || 0);
      const endMin = parseInt(eParts[0]) * 60 + parseInt(eParts[1] || 0);
      dayEvents.push({ lesson, startMin, endMin });
    });

    dayEvents.sort((a, b) => a.startMin - b.startMin);
    dayEvents.forEach((ev, i) => {
      let overlapIdx = 0;
      for (let j = 0; j < i; j++) {
        if (dayEvents[j].endMin > ev.startMin) {
          overlapIdx = (dayEvents[j].overlapIdx || 0) + 1;
        }
      }
      ev.overlapIdx = overlapIdx;
    });

    dayEvents.forEach(ev => {
      const topPx = ((ev.startMin / 60) - minH) * PX_PER_HOUR;
      const heightPx = Math.max(((ev.endMin - ev.startMin) / 60) * PX_PER_HOUR, 24);
      const whoCls = getWhoClass(ev.lesson.who);
      const whoCalCls = whoCls === 'brother' ? 'who-brother' : whoCls === 'sister' ? 'who-sister' : 'who-both';

      const hasOverlap = dayEvents.filter(other => other !== ev && other.startMin < ev.endMin && other.endMin > ev.startMin).length > 0;
      let overlapStyle = '';
      if (hasOverlap) {
        const overlapGroup = dayEvents.filter(other => other.startMin < ev.endMin && other.endMin > ev.startMin);
        const myIdx = overlapGroup.indexOf(ev);
        const total = overlapGroup.length;
        const widthPct = 100 / total;
        const leftPct = myIdx * widthPct;
        overlapStyle = `left:calc(${leftPct}% + 2px);right:calc(${100 - leftPct - widthPct}% + 2px);`;
      }

      const whoEmoji = getWhoEmoji(ev.lesson.who);
      const schoolTip = ev.lesson.school ? '\\n教室: ' + ev.lesson.school : '';
      const addressTip = ev.lesson.address ? '\\n場所: ' + ev.lesson.address : '';
      const feeTip = ev.lesson.fee ? '\\n月謝: ' + parseInt(ev.lesson.fee).toLocaleString() + '円' : '';
      const memoTip = ev.lesson.memo ? '\\nメモ: ' + ev.lesson.memo : '';
      const tooltip = `[${ev.lesson.id}] ${ev.lesson.name}\\n対象: ${ev.lesson.who}\\n時間: ${ev.lesson.start}〜${ev.lesson.end}${schoolTip}${addressTip}${feeTip}${memoTip}`;

      html += `<div class="cal-event ${whoCalCls}" style="top:${topPx}px;height:${heightPx}px;${overlapStyle}" title="${tooltip}">`;
      const schoolSuffix = ev.lesson.school ? '【' + ev.lesson.school + '】' : '';
      html += `<div class="cal-event-name">${ev.lesson.id} ${ev.lesson.name}${schoolSuffix}</div>`;
      if (heightPx >= 34) {
        html += `<div class="cal-event-who">${whoEmoji} ${ev.lesson.who}</div>`;
      }
      if (heightPx >= 56) {
        html += `<div class="cal-event-detail">${ev.lesson.start}〜${ev.lesson.end}</div>`;
      }
      html += `</div>`;
    });

    html += `</div>`;
  });
  html += `</div></div>`;

  // Day counts
  html += `<div class="day-counts">`;
  DAYS.forEach(d => {
    const cnt = stats.dayCounts[d] || 0;
    const cls = cnt >= 3 ? 'overload' : cnt > 0 ? 'has-items' : '';
    html += `<div class="day-count-item ${cls}"><span class="count">${cnt}</span>${d}</div>`;
  });
  html += `</div>`;

  // Stats
  html += `<div class="stats-row">
    <div class="stat-box"><div class="stat-num">${stats.total}</div><div class="stat-label">合計件数</div></div>
    <div class="stat-box"><div class="stat-num ${stats.fee > (parseInt(appData.conditions.budget)||Infinity) ? 'warn' : ''}">${stats.fee ? stats.fee.toLocaleString() : '-'}</div><div class="stat-label">月謝合計(円)</div></div>
    <div class="stat-box" style="border-left:3px solid var(--sister)"><div class="stat-num">${stats.sisterCount}</div><div class="stat-label">${appData.family.sister ? appData.family.sister.name : '姉'}の件数</div></div>
    <div class="stat-box" style="border-left:3px solid var(--brother)"><div class="stat-num">${stats.brotherCount}</div><div class="stat-label">${appData.family.brother ? appData.family.brother.name : '弟'}の件数</div></div>
  </div>`;

  html += `</div></div>`;
  grid.innerHTML = html;
}

function togglePatternId(patKey, lessonId) {
  const ids = appData.patterns[patKey].ids;
  const idx = ids.indexOf(lessonId);
  if (idx >= 0) ids.splice(idx, 1);
  else ids.push(lessonId);
  saveToServer();
  renderPatterns();
}

function calcStats(selectedIds) {
  let total = 0, fee = 0, sisterCount = 0, brotherCount = 0;
  const dayCounts = {};
  DAYS.forEach(d => { dayCounts[d] = 0; });
  
  selectedIds.forEach(id => {
    const lesson = appData.lessons.find(l => l.id === id);
    if (!lesson) return;
    total++;
    if (lesson.fee) fee += parseInt(lesson.fee) || 0;
    if (lesson.day) dayCounts[lesson.day] = (dayCounts[lesson.day]||0) + 1;
    const wCls = getWhoClass(lesson.who);
    if (wCls === 'sister' || wCls === 'both') sisterCount++;
    if (wCls === 'brother' || wCls === 'both') brotherCount++;
  });
  return { total, fee, sisterCount, brotherCount, dayCounts };
}

// =========== Family ===========
function renderFamily() {
  const container = document.getElementById('family-list');
  const members = [
    { key: 'papa', icon: '👨', bg: '#e8f2fb' },
    { key: 'mama', icon: '👩', bg: '#fdf0f3' },
    { key: 'sister', icon: '👧', bg: 'var(--sister-bg)', hasBirthday: true },
    { key: 'brother', icon: '👶', bg: 'var(--brother-bg)', hasBirthday: true },
  ];
  let html = '';
  members.forEach(m => {
    const data = appData.family[m.key] || {};
    html += `<div style="padding:16px;border-radius:8px;background:${m.bg};">
      <div style="font-weight:700;margin-bottom:8px;">${m.icon} ${data.name || m.key}</div>
      <div class="form-grid" style="grid-template-columns:repeat(auto-fit,minmax(160px,1fr))">
        <div class="form-group">
          <label>呼び名</label>
          <input value="${data.name || ''}" onchange="updateFamily('${m.key}','name',this.value)" placeholder="名前">
        </div>`;
    if (m.hasBirthday) {
      html += `<div class="form-group">
          <label>生年月日</label>
          <input type="date" value="${data.birthday || ''}" onchange="updateFamily('${m.key}','birthday',this.value)">
        </div>`;
    }
    html += `<div class="form-group"${!m.hasBirthday ? ' style="grid-column:span 2"' : ''}>
          <label>メモ</label>
          <input value="${data.info || ''}" onchange="updateFamily('${m.key}','info',this.value)" placeholder="職業・園など">
        </div>
      </div>
    </div>`;
  });
  container.innerHTML = html;
}

function updateFamily(memberKey, field, value) {
  if (!appData.family[memberKey]) appData.family[memberKey] = {};
  const oldName = appData.family[memberKey].name || '';
  appData.family[memberKey][field] = value;

  // When name changes, update lesson who fields and pattern references
  if (field === 'name' && oldName && oldName !== value) {
    const otherKey = memberKey === 'sister' ? 'brother' : 'sister';
    const otherName = appData.family[otherKey] ? appData.family[otherKey].name : '';
    const oldBothName = oldName + '＋' + otherName;
    const oldBothNameRev = otherName + '＋' + oldName;
    const newBothName = value + '＋' + otherName;
    const newBothNameFromOther = otherName + '＋' + value;

    appData.lessons.forEach(lesson => {
      if (lesson.who === oldName) {
        lesson.who = value;
      } else if (lesson.who === oldBothName || lesson.who === oldBothNameRev) {
        lesson.who = memberKey === 'sister' ? newBothName : newBothNameFromOther;
      }
    });
    renderLessons();
  }

  saveToServer();
  renderFamily();
}

// =========== Conditions ===========
function loadConditions() {
  const c = appData.conditions;
  document.getElementById('cond-budget').value = c.budget || '';
  document.getElementById('cond-travel').value = c.travel_limit || '';
  document.getElementById('cond-pickup').value = c.pickup_time || '';
  document.getElementById('cond-weekday').value = c.weekday_available || '';
  document.getElementById('cond-weekend').value = c.weekend_available || '';
  document.getElementById('cond-papa').value = c.papa_days || '';
}

function saveConditions() {
  appData.conditions = {
    budget: document.getElementById('cond-budget').value,
    travel_limit: document.getElementById('cond-travel').value,
    pickup_time: document.getElementById('cond-pickup').value,
    weekday_available: document.getElementById('cond-weekday').value,
    weekend_available: document.getElementById('cond-weekend').value,
    papa_days: document.getElementById('cond-papa').value,
  };
  saveToServer();
}

// =========== Save ===========
function saveToServer() {
  fetch('/api/save', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(appData)
  });
}

// =========== Migration ===========
function migrateIds() {
  const hasOldFormat = appData.lessons.some(l => l.id && /^[A-Z]\d+$/.test(l.id));
  if (!hasOldFormat) return;
  const idMap = {};
  const counters = {};
  appData.lessons.forEach(lesson => {
    const oldId = lesson.id;
    if (!oldId) return;
    const person = lesson.who || '_';
    const catLetter = getCategoryLetter(lesson.name);
    const key = person + '-' + catLetter;
    counters[key] = (counters[key] || 0) + 1;
    const newId = person + '-' + catLetter + String(counters[key]).padStart(2, '0');
    idMap[oldId] = newId;
    lesson.id = newId;
  });
  ['A', 'B', 'C'].forEach(patKey => {
    appData.patterns[patKey].ids = appData.patterns[patKey].ids.map(oldId => idMap[oldId] || oldId);
  });
  saveToServer();
  console.log('ID migration complete:', idMap);
}

// Init
renderPersonFilter();
renderLessons();
renderFamily();
loadConditions();
setupTimeInput(document.getElementById('cond-pickup'), () => saveConditions());
</script>
</body>
</html>
"""

@app.route('/')
def index():
    data = load_data()
    sync_to_sheets(data)
    return render_template_string(HTML_TEMPLATE, data_json=json.dumps(data, ensure_ascii=False))

@app.route('/api/save', methods=['POST'])
def api_save():
    data = request.get_json()
    save_data(data)
    sync_to_sheets(data)
    return jsonify({'ok': True})

@app.route('/api/data')
def api_data():
    return jsonify(load_data())

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() in ('true', '1', 'yes')
    app.run(debug=debug, host='0.0.0.0', port=port)