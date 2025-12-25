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
# [설정] 깃허브 정보
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
@st.cache_data(ttl=60) # 1분마다 캐시 초기화
def load_data():
    # 깃허브 Raw Data
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
    
    time_diff = current_time - last_update
    
    # 쿨타임 설정: 15분
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
    # 1. 최신 데이터 기준 랭킹 산정
    latest_time = df['timestamp'].max()
    ranked_df = df[df['timestamp'] == latest_time].sort_values(by=['level', 'exp'], ascending=False)
    
    # Top 20명만 자르기
    top_20_df = ranked_df.head(20)
    top_20_nicknames = top_20_df['nickname'].tolist()
    
    st.subheader(f"🏆 현재 Top 20 랭커 현황")
    
    # 2. 사이드바 검색 옵션
    st.sidebar.header("검색 옵션")
    selected_users = st.sidebar.multiselect(
        "확인할 유저를 선택하세요 (Top 20 한정)",
        top_20_nicknames, 
        default=top_20_nicknames[:20]
    )

    if selected_users:
        filtered_df = df[df['nickname'].isin(selected_users)]
        
        # -------------------------------------------------------
        # [수정됨] 3가지 보기 모드 그래프 로직
        # -------------------------------------------------------
        st.subheader("📈 경험치 경쟁 현황")
        
        view_mode = st.radio(
            "보고 싶은 그래프 종류를 선택하세요:",
            ("🏆 총 누적 경험치 (절대 순위)", "🔥 기간 내 획득 경험치 (사냥 속도)", "🤏 1등과의 격차 (추격 현황)"),
            horizontal=True
        )

        plot_df = filtered_df.copy()

        # 모드별 데이터 변환
        if "기간 내 획득" in view_mode:
            # 사냥 속도 모드: 0부터 시작
            plot_df['value'] = plot_df.groupby('nickname')['exp'].transform(lambda x: x - x.min())
            y_title = '기간 내 획득 경험치 (+)'
            title_text = '누가 가장 열심히 사냥 중인가? (획득량)'
            
        elif "1등과의 격차" in view_mode:
            # 추격 모드: 1등을 0으로 두고 격차 계산
            max_exp_per_time = plot_df.groupby('timestamp')['exp'].transform('max')
            plot_df['value'] = plot_df['exp'] - max_exp_per_time
            y_title = '1등과의 경험치 차이'
            title_text = '1등을 얼마나 따라잡았는가? (격차)'
            
        else:
            # 절대 순위 모드
            plot_df['value'] = plot_df['exp']
            y_title = '총 경험치'
            title_text = 'Top 랭커 절대 순위 변동'

        # 그래프 그리기
        fig = px.line(
            plot_df, 
            x='timestamp', 
            y='value', 
            color='nickname',
            markers=True,
            title=title_text,
            hover_data=['level', 'world', 'exp']
        )
        
        fig.update_layout(yaxis_title=y_title)
        
        # 격차 모드일 때는 0이 맨 위에 오도록 축 반전
        if "1등과의 격차" in view_mode:
            fig.update_yaxes(autorange="reversed")

        st.plotly_chart(fig, use_container_width=True)
        
        # 4. 상세 표
        with st.expander("상세 데이터 표 보기"):
            st.dataframe(filtered_df.sort_values(by='timestamp', ascending=False))
            
    else:
        st.info("왼쪽 사이드바에서 유저를 선택해주세요.")