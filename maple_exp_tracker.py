import requests
import csv
import os
import time
from datetime import datetime, timedelta
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
import pytz # timezone 처리를 위해 필요

# ==========================================
# 1. 환경 설정
# ==========================================
API_KEY = os.environ.get("NEXON_API_KEY")

HEADERS = {
    "x-nxopen-api-key": API_KEY,
    "accept": "application/json"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FILE_HISTORY = os.path.join(BASE_DIR, "exp_history.csv") # 소문자 통일

MAX_WORKERS = 20 # 서버 부하 방지를 위해 조금 줄임
RANKER_LIMIT_PER_WORLD = 50
TARGET_WORLDS = ["챌린저스", "챌린저스2", "챌린저스3", "챌린저스4"]

# URL 설정
URL_NEXON_RANKING = "https://open.api.nexon.com/maplestory/v1/ranking/overall"
URL_NEXON_OCID = "https://open.api.nexon.com/maplestory/v1/id"
URL_NEXON_BASIC = "https://open.api.nexon.com/maplestory/v1/character/basic"

# ==========================================
# 2. 유틸리티 함수
# ==========================================
def get_safe_ranking_date():
    """
    랭킹 정보 조회용 날짜 구하기 (KST 기준)
    넥슨 랭킹은 보통 오전 8시 30분에 갱신됨.
    따라서 00:00 ~ 08:30 사이에는 '어제' 랭킹도 없으므로 '그저께'를 조회해야 함.
    """
    kst = pytz.timezone('Asia/Seoul')
    now_kst = datetime.now(kst)
    
    # 오전 9시 이전이면 안전하게 2일 전 랭킹을 조회
    if now_kst.hour < 9:
        return (now_kst - timedelta(days=2)).strftime("%Y-%m-%d")
    else:
        return (now_kst - timedelta(days=1)).strftime("%Y-%m-%d")

# ==========================================
# 3. Worker 함수들
# ==========================================
def fetch_ocid_worker(row):
    try:
        # 닉네임에 특수문자가 있을 수 있으므로 quote 사용
        url = f"{URL_NEXON_OCID}?character_name={quote(row['nickname'])}"
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code == 200:
            return {
                "nickname": row['nickname'],
                "ocid": response.json().get("ocid"),
                "world": row['world'],
                "level": row['level']
            }
    except:
        pass
    return None

def fetch_exp_worker(user):
    try:
        # [핵심] date 파라미터 없이 요청 -> 실시간 최신 정보 획득
        response = requests.get(URL_NEXON_BASIC, headers=HEADERS, params={"ocid": user['ocid']}, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            user['current_level'] = int(data.get("character_level", 0))
            user['current_exp'] = int(data.get("character_exp", 0))
            return user
        elif response.status_code == 400:
            # 혹시라도 날짜 필수라고 에러나면 로그 출력
            print(f"⚠️ {user['nickname']} 400 Error (Date Required?)")
    except:
        pass
    return None

# ==========================================
# 4. 메인 로직
# ==========================================
def step1_fetch_rankings():
    """각 월드별 상위 랭커 명단 수집"""
    ranking_date = get_safe_ranking_date()
    print(f"1. 랭킹 시드 수집 중... (기준일: {ranking_date})")
    
    all_rankers = []
    
    for world in TARGET_WORLDS:
        try:
            # 랭킹 정보 요청
            params = {"date": ranking_date, "world_name": world, "page": 1}
            res = requests.get(URL_NEXON_RANKING, headers=HEADERS, params=params, timeout=10)
            
            if res.status_code == 200:
                data = res.json().get("ranking", [])
                # 설정한 인원수만큼만 가져오기
                for char in data[:RANKER_LIMIT_PER_WORLD]:
                    all_rankers.append(char)
                print(f"   - {world}: {len(data[:RANKER_LIMIT_PER_WORLD])}명 확보")
            else:
                print(f"   - {world}: 조회 실패 (Code {res.status_code})")
        except Exception as e:
            print(f"   - {world}: 에러 발생 ({e})")
            
    return all_rankers

def main():
    # API 키 확인
    if not API_KEY:
        print("🚨 API Key가 없습니다. GitHub Secrets를 확인하세요.")
        return

    # 1. 랭킹 데이터 확보
    raw_rankers = step1_fetch_rankings()
    if not raw_rankers:
        print("❌ 랭킹 데이터를 가져오지 못했습니다. (점검 중이거나 날짜 문제)")
        return
    print(f"-> 총 {len(raw_rankers)}명의 랭커를 추적합니다.")

    # 2. OCID 변환
    print("2. OCID 변환 중...")
    users_with_ocid = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_ocid_worker, {'nickname': r['character_name'], 'world': r['world_name'], 'level': r['character_level']}) for r in raw_rankers]
        for future in as_completed(futures):
            res = future.result()
            if res: users_with_ocid.append(res)
    
    print(f"-> {len(users_with_ocid)}명 OCID 확보 완료")

    # 3. 실시간 경험치 조회
    print("3. 실시간 경험치 조회 중...")
    current_status = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_exp_worker, u) for u in users_with_ocid]
        for future in as_completed(futures):
            res = future.result()
            if res and 'current_exp' in res:
                current_status.append(res)
    
    # 4. 데이터 저장
    if current_status:
        print(f"4. 데이터 {len(current_status)}건 저장 중...")
        
        file_exists = os.path.isfile(FILE_HISTORY)
        # UTC 시간으로 저장 (app.py에서 +9 보정하므로)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            with open(FILE_HISTORY, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                
                # 파일이 없으면 헤더 작성
                if not file_exists:
                    writer.writerow(["timestamp", "nickname", "world", "level", "exp"])
                    
                for user in current_status:
                    writer.writerow([
                        now_str,
                        user['nickname'],
                        user['world'],
                        user['current_level'],
                        user['current_exp']
                    ])
            print("💾 exp_history.csv 저장 완료!")
        except Exception as e:
            print(f"❌ 파일 저장 실패: {e}")
    else:
        print("⚠️ 저장할 데이터가 없습니다.")

if __name__ == "__main__":
    main()