import streamlit as st
import pandas as pd
import plotly.express as px
import os

# 페이지 기본 설정
st.set_page_config(page_title="메이플 랭커 경험치 추적기", layout="wide")

# 제목
st.title("🍁 챌린저스 월드 경험치 추이 대시보드")
st.write("30분 간격으로 수집된 랭커들의 경험치 변화를 보여줍니다.")

# [수정된 load_data 함수]
@st.cache_data(ttl=600)
def load_data():
    # 깃허브의 Raw Data 주소를 직접 입력합니다.
    # 대소문자(E vs e)가 중요하니, 아래 두 주소 중 웹브라우저에서 열리는 주소를 사용하세요.
    
    # 시도 1: 소문자 (사용자님이 말씀하신 이름)
    url = "https://raw.githubusercontent.com/djhfkgsk/maple-exp-tracker/master/exp_history.csv"
    
    # 시도 2: 대문자 (스크린샷에 보이는 이름) - 만약 위 주소가 안 되면 이걸 주석 해제해서 쓰세요
    # url = "https://raw.githubusercontent.com/djhfkgsk/maple-exp-tracker/master/Exp_history.csv"

    try:
        df = pd.read_csv(url)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        return df
    except Exception as e:
        # 에러가 나면 화면에 출력해서 원인을 확인
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
    
    # 선택 가능한 목록을 '전체'가 아닌 'Top 20'으로 제한
    selected_users = st.sidebar.multiselect(
        "확인할 유저를 선택하세요 (Top 20 한정)",
        top_20_nicknames,  # 선택지는 20명뿐
        default=top_20_nicknames[:20] # 기본적으로 20명
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
    # 1. 최신 데이터 기준 상위 랭커 목록 추출
    latest_time = df['timestamp'].max()
    latest_df = df[df['timestamp'] == latest_time].sort_values(by=['level', 'exp'], ascending=False)
    
    st.subheader(f"📊 현재 수집된 인원: {len(latest_df)}명")
    
    # 2. 유저 선택 필터 (사이드바)
    st.sidebar.header("검색 옵션")
    
    # 닉네임 목록 가져오기 (가나다순 정렬)
    all_users = sorted(df['nickname'].unique())
    
    # 기본적으로 상위 5명을 선택해둠
    default_users = latest_df['nickname'].head(20).tolist()
    
    selected_users = st.sidebar.multiselect(
        "확인할 유저를 선택하세요 (복수 선택 가능)",
        all_users,
        default=default_users
    )

    if selected_users:
        # 선택한 유저의 데이터만 필터링
        filtered_df = df[df['nickname'].isin(selected_users)]
        
        # 3. 그래프 그리기 (Plotly 사용 - 줌/팬 가능)
        fig = px.line(
            filtered_df, 
            x='timestamp', 
            y='exp', 
            color='nickname',
            markers=True,
            title='시간대별 경험치 변화',
            hover_data=['level', 'world'] # 마우스 올리면 레벨도 보이게
        )
        
        # 그래프 보여주기
        st.plotly_chart(fig, use_container_width=True)
        
        # 4. 데이터 표로 보여주기
        with st.expander("상세 데이터 표 보기"):
            st.dataframe(filtered_df.sort_values(by='timestamp', ascending=False))
            
    else:
        st.info("왼쪽 사이드바에서 유저를 선택해주세요.")