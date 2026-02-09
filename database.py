import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import bcrypt
import pandas as pd
import io
import datetime
from urllib.parse import quote

@st.cache_resource
def get_spreadsheet():
    """Google Spreadsheet 연결 객체 캐싱"""
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    try:
        # secrets 존재 여부를 안전하게 확인
        gcp_info = st.secrets.get("gcp_service_account")
        if not gcp_info:
            return None
            
        info = dict(gcp_info)
        if "private_key" in info:
            info["private_key"] = info["private_key"].replace("\\n", "\n").strip()
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open("VoiceGrape_DB")
    except Exception as e:
        st.error(f"DB 연결 실패: {e}")
        return None

def connect_to_gsheets(worksheet_name="records"):
    spreadsheet = get_spreadsheet()
    if spreadsheet is None: return None
    try:
        return spreadsheet.worksheet(worksheet_name)
    except gspread.exceptions.WorksheetNotFound:
        if worksheet_name == "records":
            new_sheet = spreadsheet.add_worksheet(title="records", rows=1000, cols=14)
            new_sheet.append_row(["timestamp", "name", "mean_pitch", "mean_f1", "mean_f2", "female_ratio", "male_ratio", "estimated_age", "mean_hnr", "jitter", "shimmer", "speech_rate", "condition_score", "passage_text"])
            return new_sheet
        elif worksheet_name == "favorites":
            new_sheet = spreadsheet.add_worksheet(title="favorites", rows=1000, cols=2)
            new_sheet.append_row(["name", "text"])
            return new_sheet
        elif worksheet_name == "users":
            new_sheet = spreadsheet.add_worksheet(title="users", rows=1000, cols=6)
            new_sheet.append_row(["username", "password", "created_at", "last_login", "records", "league"])
            return new_sheet
        return None

@st.cache_data(ttl=10)
def run_gsheets_query(_sheet, query):
    try:
        if _sheet is None: return pd.DataFrame()
        ss_id = _sheet.spreadsheet.id
        ws_id = _sheet.id
        url = f"https://docs.google.com/spreadsheets/d/{ss_id}/gviz/tq?tqx=out:csv&gid={ws_id}&headers=1&tq={quote(query)}"
        response = _sheet.spreadsheet.client.request('get', url)
        if response.status_code == 200:
            df = pd.read_csv(io.StringIO(response.text), dtype=str)
            df.columns = [c.strip() for c in df.columns]
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"쿼리 실행 오류: {e}")
        return pd.DataFrame()

def check_user_exists(name):
    sheet_users = connect_to_gsheets("users")
    if sheet_users:
        safe_name = name.replace("'", "''")
        query = f"SELECT A WHERE A = '{safe_name}'"
        df = run_gsheets_query(sheet_users, query)
        if not df.empty: return True
    return False

def create_user(name, password):
    if check_user_exists(name): return False, "이미 존재하는 사용자 이름입니다."
    sheet_users = connect_to_gsheets("users")
    if not sheet_users: return False, "DB 연결 실패"
    try:
        created_at = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        sheet_users.append_row([name, f"'{hashed_pw}", created_at, "", 0, "🌱 새싹"])
        st.cache_data.clear()
        return True, "계정이 생성되었습니다. 로그인해주세요."
    except Exception as e: return False, f"계정 생성 실패: {e}"

def update_last_login(name):
    sheet_users = connect_to_gsheets("users")
    if not sheet_users: return
    try:
        cell = sheet_users.find(name, in_column=1)
        if cell:
            now_str = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
            sheet_users.update_cell(cell.row, 4, now_str)
    except: pass

def update_user_league(name, new_count=None):
    sheet_users = connect_to_gsheets("users")
    if not sheet_users: return
    try:
        count = new_count if new_count is not None else get_user_record_count(name)
        league = get_league_from_count(count)
        cell = sheet_users.find(name, in_column=1)
        if cell:
            sheet_users.update_cell(cell.row, 5, count)
            sheet_users.update_cell(cell.row, 6, league)
    except: pass

def verify_login(name, password):
    sheet_users = connect_to_gsheets("users")
    if sheet_users:
        safe_name = name.replace("'", "''")
        query = f"SELECT * WHERE A = '{safe_name}'"
        df = run_gsheets_query(sheet_users, query)
        if not df.empty:
            stored_pwd = str(df.iloc[0, 1]).strip()
            if stored_pwd.startswith("'"): stored_pwd = stored_pwd[1:]
            try:
                if bcrypt.checkpw(password.encode('utf-8'), stored_pwd.encode('utf-8')):
                    last_login = str(df.iloc[0, 3]) if len(df.columns) > 3 and pd.notna(df.iloc[0, 3]) else "첫 로그인"
                    return True, last_login
            except:
                if stored_pwd == str(password).strip():
                    last_login = str(df.iloc[0, 3]) if len(df.columns) > 3 and pd.notna(df.iloc[0, 3]) else "첫 로그인"
                    return True, last_login
    return False, None

def save_to_history(name, metrics, passage_text):
    sheet = connect_to_gsheets("records")
    if sheet is None: return False, "DB 연결 불가"
    name = name.strip()
    current_count = get_user_record_count(name)
    data_row = [metrics["timestamp"], name, float(metrics["mean_pitch"]), float(metrics["mean_f1"]), float(metrics["mean_f2"]), float(metrics["female_ratio"]), float(metrics["male_ratio"]), int(metrics["estimated_age"]), float(metrics["mean_hnr"]), float(metrics["jitter"]), float(metrics["shimmer"]), float(metrics["speech_rate"]), float(metrics["condition_score"]), str(passage_text)]
    try:
        sheet.append_row(data_row)
        st.cache_data.clear()
        update_user_league(name, current_count + 1)
        return True, "성공"
    except Exception as e: return False, f"저장 오류: {e}"

def load_history(name, password):
    sheet = connect_to_gsheets("records")
    if sheet is None: return [], True
    name = name.strip()
    if not name: return [], True
    safe_name = name.replace("'", "''")
    query = f"SELECT * WHERE B = '{safe_name}'"
    user_df = run_gsheets_query(sheet, query)
    if user_df.empty: return [], True
    return user_df.to_dict('records'), True

def load_favorites(name):
    if not name: return []
    sheet = connect_to_gsheets("favorites")
    if sheet is None: return []
    safe_name = name.replace("'", "''")
    query = f"SELECT B WHERE A = '{safe_name}'"
    df = run_gsheets_query(sheet, query)
    if df.empty: return []
    return df.iloc[:, 0].unique().tolist()

def save_favorite(name, text):
    sheet = connect_to_gsheets("favorites")
    if sheet is None: return False, "즐겨찾기 시트(favorites)를 찾을 수 없습니다."
    try:
        sheet.append_row([name, text])
        st.cache_data.clear()
        return True, "즐겨찾기에 저장되었습니다!"
    except Exception as e: return False, f"저장 실패: {e}"

def delete_favorite(name, text):
    sheet = connect_to_gsheets("favorites")
    if sheet is None: return False, "즐겨찾기 시트를 찾을 수 없습니다."
    try:
        all_data = sheet.get_all_values()
        rows_to_delete = [idx for idx, row in enumerate(all_data[1:], start=2) if len(row) >= 2 and row[0] == name and row[1] == text]
        if not rows_to_delete: return False, "삭제할 문구를 찾을 수 없습니다."
        for idx in reversed(rows_to_delete): sheet.delete_rows(idx)
        st.cache_data.clear()
        return True, "즐겨찾기에서 삭제되었습니다."
    except Exception as e: return False, f"삭제 실패: {e}"

def reset_user_data(name):
    name = name.strip()
    if not name: return False, "이름을 입력해주세요."
    try:
        sheet_records = connect_to_gsheets("records")
        if sheet_records:
            all_records = sheet_records.get_all_values()
            rows_to_del = [i for i, row in enumerate(all_records, 1) if len(row) > 1 and row[1] == name]
            for idx in reversed(rows_to_del): sheet_records.delete_rows(idx)
        sheet_favs = connect_to_gsheets("favorites")
        if sheet_favs:
            all_favs = sheet_favs.get_all_values()
            rows_to_del = [i for i, row in enumerate(all_favs, 1) if len(row) > 0 and row[0] == name]
            for idx in reversed(rows_to_del): sheet_favs.delete_rows(idx)
        st.cache_data.clear()
        return True, f"'{name}'님의 모든 데이터가 초기화되었습니다."
    except Exception as e: return False, f"초기화 중 오류 발생: {e}"

def admin_update_user_password(name, new_password):
    sheet_users = connect_to_gsheets("users")
    if not sheet_users: return False, "DB 연결 실패"
    try:
        cell = sheet_users.find(name, in_column=1)
        if not cell: return False, "해당 사용자를 찾을 수 없습니다."
        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        sheet_users.update_cell(cell.row, 2, f"'{hashed_pw}")
        st.cache_data.clear()
        return True, f"'{name}'님의 비밀번호가 성공적으로 변경되었습니다."
    except Exception as e: return False, f"비밀번호 변경 중 오류: {e}"

def update_user_password(name, current_password, new_password):
    sheet_users = connect_to_gsheets("users")
    if not sheet_users: return False, "DB 연결 실패"
    try:
        cell = sheet_users.find(name, in_column=1)
        if not cell: return False, "사용자를 찾을 수 없습니다."
        stored_hashed_pw = sheet_users.cell(cell.row, 2).value
        if stored_hashed_pw.startswith("'"): stored_hashed_pw = stored_hashed_pw[1:]
        try: is_valid = bcrypt.checkpw(current_password.encode('utf-8'), stored_hashed_pw.encode('utf-8'))
        except: is_valid = (stored_hashed_pw == str(current_password).strip())
        if not is_valid: return False, "현재 비밀번호가 일치하지 않습니다."
        hashed_new = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        sheet_users.update_cell(cell.row, 2, f"'{hashed_new}")
        st.cache_data.clear()
        return True, "비밀번호가 성공적으로 변경되었습니다."
    except Exception as e: return False, f"오류 발생: {e}"

def admin_delete_specific_record(name, timestamp):
    sheet = connect_to_gsheets("records")
    if not sheet: return False, "DB 연결 실패"
    try:
        all_values = sheet.get_all_values()
        for idx, row in enumerate(all_values, 1):
            if len(row) > 1 and row[1] == name and row[0] == timestamp:
                sheet.delete_rows(idx)
                st.cache_data.clear()
                return True, f"[{timestamp}] 기록이 삭제되었습니다."
        return False, "삭제할 기록을 찾을 수 없습니다."
    except Exception as e: return False, f"기록 삭제 중 오류: {e}"

def admin_set_user_league(name, target_league):
    target_counts = {"🌱 새싹": 0, "🥉 브론즈": 5, "🥈 실버": 20, "🥇 골드": 50, "💎 다이아몬드": 100}
    target_count = target_counts.get(target_league, 0)
    try:
        update_user_league(name, target_count)
        st.cache_data.clear()
        return True, f"사용자의 분석 횟수를 {target_count}회로 변경하여 {target_league} 등급으로 조정했습니다."
    except Exception as e: return False, f"등급 조정 실패: {e}"

def get_user_record_count(name):
    sheet_users = connect_to_gsheets("users")
    if sheet_users:
        safe_name = name.replace("'", "''")
        query = f"SELECT E WHERE A = '{safe_name}'"
        df = run_gsheets_query(sheet_users, query)
        if not df.empty:
            val = df.iloc[0, 0]
            if pd.notna(val) and str(val).strip() != "":
                try: return int(float(str(val)))
                except: pass
    sheet = connect_to_gsheets("records")
    if not sheet: return 0
    safe_name = name.replace("'", "''")
    query = f"SELECT count(A) WHERE B = '{safe_name}'"
    df = run_gsheets_query(sheet, query)
    if not df.empty:
        try: return int(df.iloc[0, 0])
        except: return 0
    return 0

def get_league_from_count(count):
    if count >= 100: return "💎 다이아몬드"
    elif count >= 50: return "🥇 골드"
    elif count >= 20: return "🥈 실버"
    elif count >= 5: return "🥉 브론즈"
    return "🌱 새싹"
