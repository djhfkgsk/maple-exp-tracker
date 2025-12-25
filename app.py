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
# [핵심] 경험치 테이블 (누적 및 퍼센트 계산용)
# ==========================================
# 1. 해당 레벨 '0%' 달성 시점의 누적 경험치 (Base EXP)
LEVEL_BASE_EXP = {
    275: 57545329506825,
    276: 68922440762335,
    277: 81437263143396,
    278: 95203567762563,
    279: 110346502843647,
    280: 127003731431838,
    281: 143660960021029
}

# 2. 다음 레벨업에 필요한 경험치 통 (Required EXP) - 퍼센트 계산용
# (제공해주신 증가율 데이터를 바탕으로 매핑)
LEVEL_REQ_EXP = {
    275: 11377111255510,
    276: 12514822381061,
    277: 13766304619167,
    278: 15142935081083,
    279: 16657228589191,
    280: 18322951448110, # (추정치) 280구간
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
        
        # 데이터 전처리 함수
        def process_user_data(row):
            base = LEVEL_BASE_EXP.get(row['level'], 0)
            req = LEVEL_REQ_EXP.get(row['level'], 1) # 0으로 나누기 방지
            
            total_exp = base + row['exp']
            percent = (row['exp'] / req) * 100
            
            return pd.Series([total_exp, percent])
        
        # total_exp와 exp_percent 컬럼 동시 생성
        df[['total_exp', 'exp_percent']] = df.apply(process_user_data, axis=1)
        
        # 퍼센트 소수점 정리 (보기 좋게)
        df['exp_percent_str'] = df['exp_percent'].map('{:.3f}%'.format)
        
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
    # 1. 랭킹 산정 및 순위 매핑
    latest_time = df['timestamp'].max()
    latest_ranking_df = df[df['timestamp'] == latest_time].sort_values(by='total_exp', ascending=False)
    
    rank_map = {row['nickname']: i+1 for i, row in enumerate(latest_ranking_df.to_dict('records'))}
    
    # Top 15명 추출
    top_15_df = latest_ranking_df.head(15)
    top_15_nicknames = top_15_df['nickname'].tolist()
    
    st.subheader(f"🏆 현재 Top 15 랭커 현황")
    
    # 2. 사이드바 검색 옵션
    st.sidebar.header("검색 옵션")
    
    def format_func(nickname):
        rank = rank_map.get(nickname, 999)
        return f"{rank}위 {nickname}"

    selected_users = st.sidebar.multiselect(
        "확인할 유저를 선택하세요 (Top 15 한정)",
        top_15_nicknames, 
        default=top_15_nicknames[:15],
        format_func=format_func
    )

    if selected_users:
        user_filtered_df = df[df['nickname'].isin(selected_users)].copy()
        
        # 그래프 범례용 이름 생성 (순위 + 닉네임 + 현재%)
        # 최신 퍼센트를 이름 옆에 붙여주면 더 직관적임
        latest_stats = user_filtered_df[user_filtered_df['timestamp'] == latest_time].set_index('nickname')['exp_percent_str']
        
        user_filtered_df['display_name'] = user_filtered_df.apply(
            lambda x: f"{rank_map.get(x['nickname'], 999)}위 {x['nickname']}", axis=1
        )

        st.divider()
        
        # -------------------------------------------------------
        # 시간 구간 슬라이더
        # -------------------------------------------------------
        min_time = user_filtered_df['timestamp'].min()
        max_time = user_filtered_df['timestamp'].max()
        
        st.subheader("⏳ 분석 구간 설정")
        
        col1, col2 = st.columns([3, 1])
        with col1:
            start_time, end_time = st.slider(
                "분석하고 싶은 시간대를 선택하세요:",
                min_value=min_time.to_pydatetime(),
                max_value=max_time.to_pydatetime(),
                value=(min_time.to_pydatetime(), max_time.to_pydatetime()),
                format="MM/DD HH:mm",
                label_visibility="collapsed"
            )
        with col2:
            st.caption(f"선택 구간: {start_time.strftime('%m/%d %H:%M')} ~ {end_time.strftime('%m/%d %H:%M')}")
        
        final_df = user_filtered_df[
            (user_filtered_df['timestamp'] >= start_time) & 
            (user_filtered_df['timestamp'] <= end_time)
        ].copy()
        
        if final_df.empty:
            st.warning("선택된 구간에 데이터가 없습니다.")
        else:
            # -------------------------------------------------------
            # [신규 기능] 사냥 효율 분석기 (Growth Stats)
            # -------------------------------------------------------
            st.subheader("📊 사냥 효율 분석 (선택 구간 기준)")
            
            # 구간 내 변동량 계산
            growth_stats = []
            for nick in selected_users:
                user_data = final_df[final_df['nickname'] == nick].sort_values('timestamp')
                if len(user_data) < 2:
                    continue
                    
                start_row = user_data.iloc[0]
                end_row = user_data.iloc[-1]
                
                # 시간 차이 (시간 단위)
                hours = (end_row['timestamp'] - start_row['timestamp']).total_seconds() / 3600
                if hours == 0: hours = 0.001 # 0 나누기 방지
                
                # 경험치 획득량
                gained_exp = end_row['total_exp'] - start_row['total_exp']
                
                # 시간당 획득량
                exp_per_hour = gained_exp / hours
                
                # 시간당 퍼센트 (%/hr) - 현재 레벨 통 기준
                # 주의: 레벨업을 했더라도 '현재 레벨' 기준으로 환산해서 보여주는 게 일반적임
                current_req = LEVEL_REQ_EXP.get(end_row['level'], 1)
                percent_per_hour = (exp_per_hour / current_req) * 100
                
                growth_stats.append({
                    "랭킹": rank_map.get(nick, 999),
                    "닉네임": nick,
                    "레벨": f"{end_row['level']} ({end_row['exp_percent_str']})",
                    "구간 획득 경험치": f"{gained_exp:,}",
                    "🔥 시간당 경험치": f"{int(exp_per_hour):,}/hr",
                    "⚡ 시간당 속도": f"+{percent_per_hour:.3f}%/hr" # 핵심 지표
                })
            
            if growth_stats:
                stats_df = pd.DataFrame(growth_stats).sort_values("랭킹")
                st.dataframe(stats_df, hide_index=True, use_container_width=True)
            else:
                st.info("효율을 계산하기에 데이터가 충분하지 않습니다. (최소 2개 이상의 시점 필요)")

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

            sorted_legends = sorted(plot_df['display_name'].unique(), key=lambda x: int(x.split('위')[0]))

            fig = px.line(
                plot_df, 
                x='timestamp', 
                y='value', 
                color='display_name',
                markers=True,
                title=title_text,
                # 툴팁에 퍼센트 정보 추가
                hover_data={
                    'timestamp': '|%m-%d %H:%M',
                    'level': True,
                    'exp_percent_str': True, # 퍼센트 표시
                    'value': True,
                    'display_name': False
                },
                category_orders={"display_name": sorted_legends}
            )
            
            fig.update_layout(yaxis_title=y_title)
            
            if "1등과의 격차" in view_mode:
                fig.update_yaxes(autorange="reversed")

            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("상세 데이터 표 보기"):
                # 표에도 보기 좋게 컬럼 정리
                display_cols = ['timestamp', 'nickname', 'level', 'exp_percent_str', 'exp', 'total_exp']
                st.dataframe(final_df[display_cols].sort_values(by='timestamp', ascending=False), use_container_width=True)
            
    else:
        st.info("왼쪽 사이드바에서 유저를 선택해주세요.")