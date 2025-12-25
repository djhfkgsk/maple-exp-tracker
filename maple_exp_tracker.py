import os
import pandas as pd
import asyncio
import aiohttp
from datetime import datetime

# ==========================================
# [설정] API 키 및 유저 목록
# ==========================================
API_KEY = os.environ.get('NEXON_API_KEY')
HEADERS = {
    "x-nxopen-api-key": API_KEY,
    "accept": "application/json"
}

# 추적할 닉네임 리스트 (200명 리스트 꼭 채워넣으세요!)
NICKNAMES = [
    "캡틴김지명", "춘123자", "뉴비챌붕잉", "진캐12움", "구떼온",
    "후닝꽁꽁", "RetroArk", "제는맘", "욱브은월", "레거시",
    "챌섭제논싫어", "슐넌", "헌터램지", "루미너스zxcz", "크로아마세",
    "휴양림리움", "뽀꿈", "아델", "호영", "메르세데스"
    # ... 여기에 나머지 닉네임 추가 ...
]

async def fetch_user_data(session, nickname):
    # 1. OCID 조회
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

    # 2. 캐릭터 정보 조회 (날짜 파라미터 삭제 -> 최신 정보 요청)
    info_url = "https://open.api.nexon.com/maplestory/v1/character/basic"
    
    try:
        # params에서 "date"를 제거했습니다.
        async with session.get(info_url, params={"ocid": ocid}, headers=HEADERS) as resp:
            if resp.status != 200:
                print(f"❌ {nickname}: 정보 조회 실패 (Code: {resp.status})")
                # 만약 날짜 필수라고 에러가 나면, 넥슨 API 특성상 어쩔 수 없이 '어제'를 넣어야 합니다.
                # 하지만 사용자님 의견대로 일단 빼고 시도합니다.
                return None
            
            char_data = await resp.json()
            
            return {
                # UTC 시간 저장 -> app.py에서 +9시간 보정
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
                "nickname": nickname,
                "world": char_data.get("character_world_name", "Unknown"),
                "level": char_data.get("character_level", 0),
                "exp": char_data.get("character_exp", 0)
            }
    except Exception as e:
        print(f"❌ {nickname}: 정보 조회 에러 - {e}")
        return None

async def main():
    file_name = "exp_history.csv" # 소문자 유지
    
    if os.path.exists(file_name):
        df_history = pd.read_csv(file_name)
    else:
        df_history = pd.DataFrame(columns=["timestamp", "nickname", "world", "level", "exp"])

    print(f"🚀 {len(NICKNAMES)}명의 최신 데이터 수집 시작...")
    
    if not API_KEY:
        print("🚨 API KEY가 없습니다! Settings > Secrets를 확인하세요.")
        return

    sem = asyncio.Semaphore(10)

    async def fetch_with_sem(session, nickname):
        async with sem:
            return await fetch_user_data(session, nickname)

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_with_sem(session, name) for name in NICKNAMES]
        results = await asyncio.gather(*tasks)

    valid_data = [r for r in results if r is not None]
    
    print(f"✅ 수집 완료: {len(valid_data)}/{len(NICKNAMES)} 성공")

    if valid_data:
        new_df = pd.DataFrame(valid_data)
        updated_df = pd.concat([df_history, new_df], ignore_index=True)
        updated_df.to_csv(file_name, index=False, encoding='utf-8-sig')
        print("💾 데이터 저장 완료!")
    else:
        print("⚠️ 저장할 새로운 데이터가 없습니다.")

if __name__ == "__main__":
    asyncio.run(main())