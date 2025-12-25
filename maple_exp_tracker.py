import requests
import csv
import time
import os
from datetime import datetime, timedelta
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==========================================
# 1. 환경 설정
# ==========================================
# [중요] 깃허브 설정(Secrets)에서 불러오도록 변경
API_KEY = os.environ.get("NEXON_API_KEY") 

# 로컬 테스트용: 깃허브가 아닐 땐 빈 문자열 방지 (필요시 여기에 키 입력해서 테스트 가능)
if not API_KEY:
    # print("경고: API 키가 없습니다. 로컬 실행이라면 os.environ을 설정하거나 여기에 키를 넣으세요.")
    API_KEY = "내_API_키_직접_입력_테스트용" 

HEADERS = {
    "x-nxopen-api-key": API_KEY,
    "accept": "application/json"
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# [변경] 누적 데이터를 저장할 파일명
FILE_HISTORY = os.path.join(BASE_DIR, "exp_history.csv") 

# 나머지 설정 동일
MAX_WORKERS = 50
RANKER_LIMIT_PER_WORLD = 50
TARGET_WORLDS = ["챌린저스", "챌린저스2", "챌린저스3", "챌린저스4"]

# URL들 동일
URL_NEXON_RANKING = "https://open.api.nexon.com/maplestory/v1/ranking/overall"
URL_NEXON_OCID = "https://open.api.nexon.com/maplestory/v1/id"
URL_NEXON_BASIC = "https://open.api.nexon.com/maplestory/v1/character/basic"

# ==========================================
# 2. Worker 함수들 (fetch_ocid_worker, fetch_exp_worker)
# ==========================================
# (기존 코드와 완전히 동일하므로 생략하지 않고 핵심만 유지)
# ... 기존 함수들 그대로 두시면 됩니다 ...
# 편의를 위해 생략 없이 전체 흐름이 이어지게 작성할게요.

def get_yesterday_str():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def fetch_ocid_worker(row):
    # ... (기존과 동일) ...
    try:
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
    # ... (기존과 동일) ...
    try:
        response = requests.get(URL_NEXON_BASIC, headers=HEADERS, params={"ocid": user['ocid']}, timeout=5)
        if response.status_code == 200:
            data = response.json()
            user['current_level'] = int(data.get("character_level", 0))
            user['current_exp'] = int(data.get("character_exp", 0))
            return user
    except:
        pass
    return None

# ==========================================
# 3. 메인 로직 (History 저장 중심)
# ==========================================
def step1_fetch_rankings():
    # ... (기존과 동일하지만 리턴값만 넘김) ...
    print("1. 랭킹 시드 수집 중...")
    date = get_yesterday_str()
    all_rankers = []
    for world in TARGET_WORLDS:
        try:
            params = {"date": date, "world_name": world, "page": 1}
            res = requests.get(URL_NEXON_RANKING, headers=HEADERS, params=params, timeout=5)
            if res.status_code == 200:
                data = res.json().get("ranking", [])
                # 넉넉하게 수집
                for char in data[:RANKER_LIMIT_PER_WORLD]:
                    all_rankers.append(char)
        except:
            pass
    return all_rankers

def main():
    # 1. 랭킹 데이터 확보
    raw_rankers = step1_fetch_rankings()
    if not raw_rankers:
        print("데이터 수집 실패")
        return

    # 2. OCID 변환
    print("2. OCID 변환 중...")
    users_with_ocid = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_ocid_worker, {'nickname': r['character_name'], 'world': r['world_name'], 'level': r['character_level']}) for r in raw_rankers]
        for future in as_completed(futures):
            res = future.result()
            if res: users_with_ocid.append(res)

    # 3. 실시간 경험치 조회
    print("3. 실시간 경험치 조회 중...")
    current_status = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(fetch_exp_worker, u) for u in users_with_ocid]
        for future in as_completed(futures):
            res = future.result()
            if res and 'current_exp' in res:
                current_status.append(res)
    
    # [핵심 변경] 데이터를 누적 저장 (Append Mode 'a')
    print(f"4. 데이터 {len(current_status)}건 저장 중...")
    
    # 파일이 없으면 헤더를 써야 함
    file_exists = os.path.isfile(FILE_HISTORY)
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(FILE_HISTORY, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        
        # 파일이 처음 생길 때만 헤더 작성
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
            
    print("완료! exp_history.csv에 저장됨.")

if __name__ == "__main__":
    main()
