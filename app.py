import streamlit as st
import pandas as pd
import plotly.express as px
import os
import requests
import json
from datetime import datetime, timedelta

# 페이지 기본 설정
st.set_page_config(page_title="메이플 랭커 경험치 추적기", layout="wide")

# ==========================================
# [설정] 깃허브 정보 (본인 아이디로 수정 불필요, 자동 적용됨)
# ==========================================
GITHUB_OWNER = "djhfkgsk"
GITHUB_REPO = "maple-exp-tracker"
WORKFLOW_FILE = "main.yml" 

# 제목
st.title("🍁 챌린저스 월드 경험치 추이 대시보드")

# ------------------------------------------
# [기능 1] 데이터 수집 요청 버튼 (사이드바)
# ------------------------------------------
st.sidebar.header("🕹️ 데이터 업데이트")

def trigger_github_action():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}"
    }
    data = {"ref": "master"} # 혹은 main
    
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.status_code

# 데이터 로드 함수 (캐시 사용)
@st.cache_data(ttl=60) # 1분마다 캐시 초기화 (버튼 누르고 빨리 반영되라고)
def load_data():
    # 깃허브 Raw Data (소문자/대문자 이슈 고려)
    url = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/master/exp_history.csv"
    try:
        df = pd.read_csv(url)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except:
        return pd.DataFrame()

df = load_data()

# 쿨타임 계산 및 버튼 표시 로직
if not df.empty:
    last_update = df['timestamp'].max()
    current_time = datetime.now()
    
    # 한국 시간 보정 (GitHub 서버는 보통 UTC 기준일 수 있으나, 단순 차이 계산은 OK)
    # 여기서는 단순하게 '마지막 데이터 시간'과 '현재 시간'의 차이를 봅니다.
    # 데이터가 15분 이내에 갱신되었다면 버튼을 잠급니다.
    time_diff = current_time - last_update
    
    # 쿨타임 설정: 15분
    # (주의: 서버 시간차 때문에 약간의 오차가 있을 수 있으나, 보통 15분이면 충분합니다)
    if time_diff < timedelta(minutes=15):
        st.sidebar.success(f"✅ 최신 상태입니다.\n({last_update.strftime('%H:%M')} 기준)")
        st.sidebar.info("데이터는 15분마다 갱신 가능합니다.")
    else:
        st.sidebar.warning(f"📉 데이터가 오래되었습니다.\n({int(time_diff.total_seconds()//60)}분 전)")
        if st.sidebar.button("🚀 데이터 수집 즉시 실행"):
            try:
                code = trigger_github_action()
                if code == 204:
                    st.toast("요청 성공! 1~2분 뒤 새로고침 하세요.", icon="🎉")
                else:
                    st.error(f"요청 실패 (코드: {code}). 설정(Secrets)을 확인하세요.")
            except Exception as e:
                st.error(f"에러 발생: {e}")
                st.info("Streamlit Secrets에 GITHUB_TOKEN이 있는지 확인해주세요.")

# ==========================================
# [기능 2] 메인 대시보드 (그래프)
# ==========================================

st.write("30분 간격으로 수집된 랭커들의 경험치 변화를 보여줍니다.")

if df.empty:
    st.warning("아직 수집된 데이터가 없습니다.")
else:
    # ... (기존 그래프 로직과 동일) ...
    latest_time = df['timestamp'].max()
    ranked_df = df[df['timestamp'] == latest_time].sort_values(by=['level', 'exp'], ascending=False)
    
    top_20_df = ranked_df.head(20)
    top_20_nicknames = top_20_df['nickname'].tolist()
    
    st.subheader(f"🏆 현재 Top 20 랭커 현황")
    
    st.sidebar.header("검색 옵션")
    selected_users = st.sidebar.multiselect(
        "확인할 유저를 선택하세요 (Top 20 한정)",
        top_20_nicknames, 
        default=top_20_nicknames[:20]
    )

    if selected_users:
        filtered_df = df[df['nickname'].isin(selected_users)]
        
        st.subheader("📈 경험치 그래프")
        show_growth_only = st.checkbox("🏁 시작점을 0으로 맞춰서 '순수 증가량'만 보기 (추천)", value=True)

        plot_df = filtered_df.copy()

        if show_growth_only:
            plot_df['exp_gained'] = plot_df.groupby('nickname')['exp'].transform(lambda x: x - x.min())
            y_axis = 'exp_gained'
            y_title = '기간 내 획득 경험치 (누적)'
        else:
            y_axis = 'exp'
            y_title = '총 경험치'

        fig = px.line(
            plot_df, 
            x='timestamp', 
            y=y_axis, 
            color='nickname',
            markers=True,
            title=f'Top 랭커 경쟁 현황 ({y_title})',
            hover_data=['level', 'world', 'exp']
        )
        fig.update_layout(yaxis_title=y_title)
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("상세 데이터 표 보기"):
            st.dataframe(filtered_df.sort_values(by='timestamp', ascending=False))
    else:
        st.info("왼쪽 사이드바에서 유저를 선택해주세요.")