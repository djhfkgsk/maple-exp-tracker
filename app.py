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

# ==========================================
# [핵심] 경험치 테이블 (누적 경험치 계산용)
# ==========================================
LEVEL_BASE_EXP = {
    275: 57545329506825,
    276: 68922440762335,
    277: 81437263143396,
    278: 95203567762563,
    279: 110346502843647,
    280: 127003731431838,
    281: 143660960021029
}

# 제목
st.title("🍁 챌린저스 월드 경험치 추이 대시보드")

# ------------------------------------------
# [기능 1] 데이터 수집 요청 버튼
# ------------------------------------------
st.sidebar.header("🕹️ 데이터 업데이트")

def trigger_github_action():
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"token {st.secrets['GITHUB_TOKEN']}"
    }
    data = {"ref": "master"}
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.status_code

@st.cache_data(ttl=60) 
def load_data():
    url = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/master/exp_history.csv"
    try:
        df = pd.read_csv(url)
        df['timestamp'] = pd.to_datetime(df['timestamp']) + timedelta(hours=9) # KST 변환
        
        # 총 누적 경험치 계산
        def calculate_total_exp(row):
            base = LEVEL_BASE_EXP.get(row['level'], 0)
            return base + row['exp']
        
        df['total_exp'] = df.apply(calculate_total_exp, axis=1)
        return df
    except:
        return pd.DataFrame()

df = load_data()

# 쿨타임 로직
if not df.empty:
    last_update = df['timestamp'].max()
    current_time_kst = datetime.now() + timedelta(hours=9)
    time_diff = current_time_kst - last_update
    
    if time_diff < timedelta(minutes=15):
        st.sidebar.success(f"✅ 최신 상태입니다.\n({last_update.strftime('%H:%M')} 기준)")
    else:
        st.sidebar.warning(f"📉 데이터가 오래되었습니다.\n({int(time_diff.total_seconds()//60)}분 전)")
        if st.sidebar.button("🚀 데이터 수집 즉시 실행"):
            try:
                code = trigger_github_action()
                if code == 204:
                    st.toast("요청 성공! 1~2분 뒤 새로고침 하세요.", icon="🎉")
                else:
                    st.error(f"요청 실패 (코드: {code})")
            except Exception as e:
                st.error(f"에러: {e}")

# ==========================================
# [기능 2] 메인 대시보드
# ==========================================

st.write("30분 간격으로 수집된 랭커들의 경험치 변화를 보여줍니다.")

if df.empty:
    st.warning("아직 수집된 데이터가 없습니다.")
else:
    # 1. 최신 데이터 기준 전체 랭킹 산정 (순위 매기기용)
    latest_time = df['timestamp'].max()
    
    # 전체 인원을 total_exp로 정렬
    latest_ranking_df = df[df['timestamp'] == latest_time].sort_values(by='total_exp', ascending=False)
    
    # [핵심] 순위 정보 매핑 (닉네임 -> 현재 순위)
    # enumerate는 0부터 시작하므로 +1 해서 1등부터 시작
    rank_map = {row['nickname']: i+1 for i, row in enumerate(latest_ranking_df.to_dict('records'))}
    
    # Top 20명 추출
    top_20_df = latest_ranking_df.head(20)
    top_20_nicknames = top_20_df['nickname'].tolist()
    
    st.subheader(f"🏆 현재 Top 20 랭커 현황")
    
    st.sidebar.header("검색 옵션")
    selected_users = st.sidebar.multiselect(
        "확인할 유저를 선택하세요 (Top 20 한정)",
        top_20_nicknames, 
        default=top_20_nicknames[:20]
    )

    if selected_users:
        user_filtered_df = df[df['nickname'].isin(selected_users)].copy()
        
        # [핵심] 닉네임을 '1위 닉네임' 형태로 변경
        # 이렇게 하면 그래프 범례(Legend)에 순위가 같이 나옵니다.
        user_filtered_df['display_name'] = user_filtered_df['nickname'].apply(
            lambda x: f"{rank_map.get(x, 999)}위 {x}"
        )

        st.divider()
        
        # -------------------------------------------------------
        # 시간 구간 슬라이더
        # -------------------------------------------------------
        min_time = user_filtered_df['timestamp'].min()
        max_time = user_filtered_df['timestamp'].max()
        
        st.subheader("⏳ 분석 구간 설정")
        
        start_time, end_time = st.slider(
            "분석하고 싶은 시간대를 선택하세요:",
            min_value=min_time.to_pydatetime(),
            max_value=max_time.to_pydatetime(),
            value=(min_time.to_pydatetime(), max_time.to_pydatetime()),
            format="MM/DD HH:mm"
        )
        
        final_df = user_filtered_df[
            (user_filtered_df['timestamp'] >= start_time) & 
            (user_filtered_df['timestamp'] <= end_time)
        ].copy()
        
        if final_df.empty:
            st.warning("선택된 구간에 데이터가 없습니다.")
        else:
            # -------------------------------------------------------
            # 그래프 로직
            # -------------------------------------------------------
            st.subheader("📈 경험치 경쟁 현황")
            
            view_mode = st.radio(
                "보고 싶은 그래프 종류를 선택하세요:",
                ("🏆 총 누적 경험치 (절대 순위)", "🔥 기간 내 획득 경험치 (사냥 속도)", "🤏 1등과의 격차 (추격 현황)"),
                horizontal=True
            )

            plot_df = final_df.copy()

            if "기간 내 획득" in view_mode:
                plot_df['value'] = plot_df.groupby('nickname')['total_exp'].transform(lambda x: x - x.min())
                y_title = '선택 구간 내 획득 경험치 (+)'
                title_text = f'해당 구간 사냥 승자는? ({start_time.strftime("%H:%M")} ~ {end_time.strftime("%H:%M")})'
                
            elif "1등과의 격차" in view_mode:
                max_exp_per_time = plot_df.groupby('timestamp')['total_exp'].transform('max')
                plot_df['value'] = plot_df['total_exp'] - max_exp_per_time
                y_title = '1등과의 경험치 차이'
                title_text = '1등을 얼마나 따라잡았는가? (격차)'
                
            else:
                plot_df['value'] = plot_df['total_exp']
                y_title = '총 누적 경험치'
                title_text = 'Top 랭커 절대 순위'

            # 범례 정렬을 위해 순서 리스트 생성 (1위, 2위, 3위... 순서대로)
            # 이걸 안 하면 1위, 10위, 11위... 2위 순서로 나옴 (문자열 정렬 때문)
            sorted_legends = sorted(plot_df['display_name'].unique(), key=lambda x: int(x.split('위')[0]))

            fig = px.line(
                plot_df, 
                x='timestamp', 
                y='value', 
                color='display_name', # [변경] 닉네임 대신 순위 포함된 이름 사용
                markers=True,
                title=title_text,
                hover_data=['level', 'world', 'exp'],
                category_orders={"display_name": sorted_legends} # [핵심] 범례 순서 강제 고정
            )
            
            fig.update_layout(yaxis_title=y_title)
            
            if "1등과의 격차" in view_mode:
                fig.update_yaxes(autorange="reversed")

            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("상세 데이터 표 보기"):
                st.dataframe(final_df.sort_values(by='timestamp', ascending=False))
            
    else:
        st.info("왼쪽 사이드바에서 유저를 선택해주세요.")