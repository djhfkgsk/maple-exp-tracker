import streamlit as st
import pandas as pd
import plotly.express as px
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
# [핵심] 경험치 테이블
# ==========================================
LEVEL_BASE_EXP = {
    275: 57545329506825,
    276: 68922440762335,
    277: 81437263143396,
    278: 95203567762563,
    279: 110346502843647,
    280: 127003731431838, # 목표 지점 (280레벨 0%)
    281: 143660960021029
}

LEVEL_REQ_EXP = {
    275: 11377111255510,
    276: 12514822381061,
    277: 13766304619167,
    278: 15142935081083,
    279: 16657228589191,
    280: 18322951448110,
}

# 280레벨 달성 기준 총 경험치
TARGET_EXP_280 = LEVEL_BASE_EXP[280]

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
        
        def process_user_data(row):
            base = LEVEL_BASE_EXP.get(row['level'], 0)
            req = LEVEL_REQ_EXP.get(row['level'], 1)
            total_exp = base + row['exp']
            percent = (row['exp'] / req) * 100
            return pd.Series([total_exp, percent])
        
        df[['total_exp', 'exp_percent']] = df.apply(process_user_data, axis=1)
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
    # 1. 랭킹 산정 (Top 15 기준)
    latest_time = df['timestamp'].max()
    latest_ranking_df = df[df['timestamp'] == latest_time].sort_values(by='total_exp', ascending=False)
    
    rank_map = {row['nickname']: i+1 for i, row in enumerate(latest_ranking_df.to_dict('records'))}
    top_15_df = latest_ranking_df.head(15)
    top_15_nicknames = top_15_df['nickname'].tolist()
    
    st.subheader(f"🏆 현재 Top 15 랭커 현황")
    
    # 사이드바
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
        user_filtered_df['display_name'] = user_filtered_df.apply(
            lambda x: f"{rank_map.get(x['nickname'], 999)}위 {x['nickname']}", axis=1
        )

        st.divider()
        st.subheader("⏳ 분석 구간 설정")
        
        min_time = user_filtered_df['timestamp'].min()
        max_time = user_filtered_df['timestamp'].max()
        
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
        
        # -------------------------------------------------------
        # Top 15 전체 백그라운드 속도 & 280 달성 예측
        # -------------------------------------------------------
        top_15_all_data = df[
            (df['nickname'].isin(top_15_nicknames)) &
            (df['timestamp'] >= start_time) &
            (df['timestamp'] <= end_time)
        ].copy()

        user_metrics = {} 
        
        for nick in top_15_nicknames:
            u_data = top_15_all_data[top_15_all_data['nickname'] == nick].sort_values('timestamp')
            if len(u_data) < 2:
                continue
            
            s_row = u_data.iloc[0]
            e_row = u_data.iloc[-1]
            
            hours = (e_row['timestamp'] - s_row['timestamp']).total_seconds() / 3600
            if hours == 0: hours = 0.001
            
            exp_diff = e_row['total_exp'] - s_row['total_exp']
            speed = exp_diff / hours
            
            # [신규 기능] 280까지 남은 시간 계산
            if e_row['total_exp'] >= TARGET_EXP_280:
                time_to_280_str = "🎉 달성 완료!"
            elif speed <= 0:
                time_to_280_str = "측정 불가 (멈춤)"
            else:
                remaining = TARGET_EXP_280 - e_row['total_exp']
                hours_left = remaining / speed
                
                days_280 = int(hours_left // 24)
                rem_hours_280 = int(hours_left % 24)
                
                if days_280 > 999: # 너무 오래 걸리면
                    time_to_280_str = "측정 불가 (너무 느림)"
                else:
                    time_to_280_str = f"D-{days_280}일 {rem_hours_280}시간"

            user_metrics[nick] = {
                'nickname': nick,
                'rank': rank_map.get(nick, 999),
                'current_total_exp': e_row['total_exp'],
                'speed': speed,
                'level_info': f"{e_row['level']} ({e_row['exp_percent_str']})",
                'gained_exp': exp_diff,
                'time_to_280': time_to_280_str # 결과 저장
            }

        sorted_metrics = sorted(user_metrics.values(), key=lambda x: x['rank'])
        overtake_info = {} 
        
        for i in range(1, len(sorted_metrics)):
            me = sorted_metrics[i]
            target = sorted_metrics[i-1]
            gap = target['current_total_exp'] - me['current_total_exp']
            speed_gap = me['speed'] - target['speed']
            
            msg = "-"
            target_name = f"{target['rank']}위 {target['nickname']}"
            
            if gap <= 0:
                msg = "이미 역전함"
            elif speed_gap <= 0:
                msg = "추월 불가 (느림)"
            else:
                hours_needed = gap / speed_gap
                days = int(hours_needed // 24)
                rem_hours = int(hours_needed % 24)
                mins = int((hours_needed * 60) % 60)
                
                time_str = []
                if days > 0: time_str.append(f"{days}일")
                if rem_hours > 0: time_str.append(f"{rem_hours}시간")
                time_str.append(f"{mins}분")
                msg = " ".join(time_str) + " 후"
            
            overtake_info[me['nickname']] = {"target": target_name, "time": msg, "gap": gap}
            
        if sorted_metrics:
            overtake_info[sorted_metrics[0]['nickname']] = {"target": "-", "time": "독주 중 👑", "gap": 0}

        # -------------------------------------------------------
        # 표 만들기
        # -------------------------------------------------------
        st.subheader("📊 사냥 효율 및 추격 현황표")
        
        display_rows = []
        for nick in selected_users:
            if nick not in user_metrics:
                continue
            u = user_metrics[nick]
            o_info = overtake_info.get(nick, {"target": "?", "time": "?", "gap": 0})
            
            current_req = LEVEL_REQ_EXP.get(int(u['level_info'].split()[0]), 1)
            percent_speed = (u['speed'] / current_req) * 100
            
            display_rows.append({
                "순위": u['rank'],
                "닉네임": nick,
                "레벨 (현재%)": u['level_info'],
                "획득 경험치": f"{int(u['gained_exp']):,}",
                "⚡ 속도 (%/hr)": f"+{percent_speed:.3f}%",
                "⏱️ 역전 예상": o_info['time'], # 이름 줄임
                "🏁 280까지": u['time_to_280'] # [신규 컬럼]
            })
            
        if display_rows:
            final_table_df = pd.DataFrame(display_rows).sort_values("순위")
            st.dataframe(
                final_table_df, 
                hide_index=True, 
                use_container_width=True,
                column_config={
                    "순위": st.column_config.NumberColumn(format="%d위"),
                    "⏱️ 역전 예상": st.column_config.TextColumn(help="바로 윗 등수를 잡는데 걸리는 시간"),
                    "🏁 280까지": st.column_config.TextColumn(help="현재 속도로 280레벨 달성까지 남은 시간")
                }
            )
        else:
            st.info("데이터가 부족하여 계산할 수 없습니다.")

        # -------------------------------------------------------
        # 그래프 그리기
        # -------------------------------------------------------
        final_df = user_filtered_df[
            (user_filtered_df['timestamp'] >= start_time) & 
            (user_filtered_df['timestamp'] <= end_time)
        ].copy()
        
        if not final_df.empty:
            st.subheader("📈 경험치 경쟁 그래프")
            
            view_mode = st.radio(
                "그래프 모드:",
                ("🏆 총 누적 경험치 (절대 순위)", "🔥 기간 내 획득 경험치 (속도)", "🤏 1등과의 격차 (추격)"),
                horizontal=True
            )

            plot_df = final_df.copy()
            
            # 툴팁용 속도 계산
            plot_df = plot_df.sort_values(by=['nickname', 'timestamp'])
            plot_df['dt'] = plot_df.groupby('nickname')['timestamp'].diff().dt.total_seconds() / 3600
            plot_df['d_exp'] = plot_df.groupby('nickname')['total_exp'].diff()
            
            def get_speed_tooltip(row):
                if pd.isna(row['dt']) or row['dt'] <= 0:
                    return "-"
                speed_per_hour = row['d_exp'] / row['dt']
                req_exp = LEVEL_REQ_EXP.get(row['level'], 1)
                percent_speed = (speed_per_hour / req_exp) * 100
                return f"+{percent_speed:.3f}%/hr"

            plot_df['speed_tooltip'] = plot_df.apply(get_speed_tooltip, axis=1)

            if "기간 내 획득" in view_mode:
                plot_df['value'] = plot_df.groupby('nickname')['total_exp'].transform(lambda x: x - x.min())
                y_title = '구간 획득 경험치 (+)'
                title_text = f'누가 제일 많이 먹었나? ({start_time.strftime("%H:%M")} ~)'
            elif "1등과의 격차" in view_mode:
                max_exp_per_time = plot_df.groupby('timestamp')['total_exp'].transform('max')
                plot_df['value'] = plot_df['total_exp'] - max_exp_per_time
                y_title = '1등과의 차이'
                title_text = '1등 따라잡기 (격차)'
            else:
                plot_df['value'] = plot_df['total_exp']
                y_title = '총 누적 경험치'
                title_text = '순위 변동 그래프'

            sorted_legends = sorted(plot_df['display_name'].unique(), key=lambda x: int(x.split('위')[0]))

            fig = px.line(
                plot_df, 
                x='timestamp', 
                y='value', 
                color='display_name',
                markers=True,
                title=title_text,
                hover_data={
                    'timestamp': '|%m-%d %H:%M', 
                    'level': True, 
                    'exp_percent_str': True, 
                    'speed_tooltip': True,
                    'value': True, 
                    'display_name': False,
                    'dt': False, 
                    'd_exp': False
                },
                category_orders={"display_name": sorted_legends}
            )
            
            fig.update_traces(
                hovertemplate="<br>".join([
                    "<b>%{x}</b>",
                    "Level: %{customdata[1]}",
                    "Exp: %{customdata[2]}",
                    "<b>⚡ 속도: %{customdata[3]}</b>",
                    "Value: %{y}"
                ])
            )
            
            fig.update_layout(yaxis_title=y_title)
            if "1등과의 격차" in view_mode:
                fig.update_yaxes(autorange="reversed")
            
            st.plotly_chart(fig, use_container_width=True)
            
    else:
        st.info("왼쪽 사이드바에서 유저를 선택해주세요.")