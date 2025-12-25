import streamlit as st
import pandas as pd
import plotly.express as px
import os

# 페이지 기본 설정
st.set_page_config(page_title="메이플 랭커 경험치 추적기", layout="wide")

# 제목
st.title("🍁 챌린저스 월드 경험치 추이 대시보드")
st.write("30분 간격으로 수집된 랭커들의 경험치 변화를 보여줍니다.")

# 데이터 불러오기 함수
@st.cache_data(ttl=600)
def load_data():
    # 깃허브의 Raw Data 주소 (소문자 버전 사용)
    url = "https://raw.githubusercontent.com/djhfkgsk/maple-exp-tracker/master/exp_history.csv"
    
    # 만약 위 주소가 안 되면 아래 대문자 주소의 주석(#)을 풀고 위를 주석 처리하세요
    # url = "https://raw.githubusercontent.com/djhfkgsk/maple-exp-tracker/master/Exp_history.csv"

    try:
        df = pd.read_csv(url)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        st.error(f"데이터를 불러오지 못했습니다. URL을 확인해주세요. 에러 내용: {e}")
        return pd.DataFrame()

df = load_data()

if df.empty:
    st.warning("아직 수집된 데이터가 없습니다. 조금만 기다려주세요!")
else:
    # 1. 최신 데이터 기준 랭킹 산정
    latest_time = df['timestamp'].max()
    
    # 전체 데이터를 레벨/경험치 순으로 정렬
    ranked_df = df[df['timestamp'] == latest_time].sort_values(by=['level', 'exp'], ascending=False)
    
    # [핵심] 상위 20명만 자르기 (Top 20)
    top_20_df = ranked_df.head(20)
    top_20_nicknames = top_20_df['nickname'].tolist()
    
    st.subheader(f"🏆 현재 Top 20 랭커 현황 (총 {len(top_20_df)}명)")
    
    # 2. 사이드바 설정
    st.sidebar.header("검색 옵션")
    
    # 선택 가능한 목록을 'Top 20'으로 제한
    selected_users = st.sidebar.multiselect(
        "확인할 유저를 선택하세요 (Top 20 한정)",
        top_20_nicknames, 
        default=top_20_nicknames[:20] # 기본적으로 20명 모두 선택
    )

    if selected_users:
        # 선택한 유저들의 '과거 기록'까지 모두 가져옴
        filtered_df = df[df['nickname'].isin(selected_users)]
        
        # 3. 그래프 그리기
        fig = px.line(
            filtered_df, 
            x='timestamp', 
            y='exp', 
            color='nickname',
            markers=True,
            title='Top 랭커 경험치 경쟁 추이',
            hover_data=['level', 'world']
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 4. 표 보여주기 (최신 순)
        with st.expander("상세 데이터 표 보기"):
            st.dataframe(filtered_df.sort_values(by='timestamp', ascending=False))
            
    else:
        st.info("왼쪽 사이드바에서 유저를 선택해주세요.")