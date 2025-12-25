import os
import pandas as pd
import asyncio
import aiohttp
from datetime import datetime
import pytz

# ==========================================
# [설정] API 키 및 유저 목록
# ==========================================
API_KEY = os.environ.get('NEXON_API_KEY')
HEADERS = {
    "x-nxopen-api-key": API_KEY
}

# 추적할 닉네임 리스트 (여기에 본인이 원하는 랭커 리스트를 넣으세요)
# 예시로 몇 명만 적어둡니다. 실제 사용하는 리스트로 교체하세요.
NICKNAMES = [
    "캡틴김지명", "춘123자", "뉴비챌붕잉", "진캐12움", "구떼온",
    "후닝꽁꽁", "RetroArk", "제는맘", "욱브은월", "레거시",
    "챌섭제논싫어", "슐넌", "헌터램지", "루미너스zxcz", "크로아마세",
    "휴양림리움", "뽀꿈", "아델", "호영", "메르세데스"
    # ... 기존에 쓰시던 200명 리스트를 여기에 넣으세요 ...
]

# ==========================================
# [핵심] 비동기 데이터 수집 함수
# ==========================================
async def fetch_user_data(session, nickname):
    # 1. OCID 조회 (닉네임 -> 고유 ID)
    ocid_url = "https://open.api.nexon.com/maplestory/v1/id"
    
    try:
        async with session.get(ocid_url, params={"character_name": nickname}, headers=HEADERS) as resp:
            if resp.status != 200:
                print(f"❌ {nickname}: OCID 조회 실패 (Code: {resp.status})")
                return None
            data = await resp.json()
            ocid = data.get('ocid')
    except Exception as e:
        print(f"❌ {nickname}: OCID 에러 - {e}")
        return None

    if not ocid:
        return None

    # 2. 캐릭터 기본 정보 조회 (레벨, 경험치 등)
    info_url = "https://open.api.nexon.com/maplestory/v1/character/basic"
    yesterday = (datetime.now(pytz.timezone('Asia/Seoul')).date() - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    
    try:
        async with session.get(info_url, params={"ocid": ocid, "date": yesterday}, headers=HEADERS) as resp:
            if resp.status != 200:
                print(f"❌ {nickname}: 정보 조회 실패 (Code: {resp.status})")
                return None
            
            char_data = await resp.json()
            
            # 필요한 데이터 추출
            return {
                "timestamp": datetime.now(pytz.timezone('Asia/Seoul')).strftime('%Y-%m-%d %H:%M:%S'),
                "nickname": nickname,
                "world": char_data.get("character_world_name", "Unknown"),
                "level": char_data.get("character_level", 0),
                "exp": char_data.get("character_exp", 0)
            }
    except Exception as e:
        print(f"❌ {nickname}: 정보 조회 에러 - {e}")
        return None

async def main():
    # 저장된 CSV가 있으면 불러오고, 없으면 새로 만듦
    file_name = "exp_history.csv" # 소문자로 통일
    
    if os.path.exists(file_name):
        df_history = pd.read_csv(file_name)
    else:
        df_history = pd.DataFrame(columns=["timestamp", "nickname", "world", "level", "exp"])

    print(f"🚀 {len(NICKNAMES)}명의 데이터 수집 시작...")
    
    # 동시 실행 제한 (Semaphore): 한 번에 10명씩만 요청 (서버 과부하 방지)
    sem = asyncio.Semaphore(10)

    async def fetch_with_sem(session, nickname):
        async with sem:
            return await fetch_user_data(session, nickname)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_with_sem(session, name) for name in NICKNAMES]
        results = await asyncio.gather(*tasks)

    # 실패한 건(None) 제외하고 성공한 것만 모으기
    valid_data = [r for r in results if r is not None]
    
    print(f"✅ 수집 완료: {len(valid_data)}/{len(NICKNAMES)} 성공")

    if valid_data:
        new_df = pd.DataFrame(valid_data)
        
        # 기존 데이터에 합치기
        updated_df = pd.concat([df_history, new_df], ignore_index=True)
        
        # 파일 저장
        updated_df.to_csv(file_name, index=False, encoding='utf-8-sig')
        print("💾 데이터 저장 완료!")
    else:
        print("⚠️ 저장할 새로운 데이터가 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())