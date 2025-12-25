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
@st.cache_data(ttl=600) # 10분마다 새로고침
def load_data():
    if not os.path.exists('exp_history.csv'):
        return pd.DataFrame()
    
    # CSV 읽기
    df = pd.read_csv('exp_history.csv')
    
    # timestamp를 날짜 형식으로 변환
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    return df

df = load_data()

if df.empty:
    st.warning("아직 수집된 데이터가 없습니다. 조금만 기다려주세요!")
else:
    # 1. 최신 데이터 기준 상위 랭커 목록 추출
    latest_time = df['timestamp'].max()
    latest_df = df[df['timestamp'] == latest_time].sort_values(by=['level', 'exp'], ascending=False)
    
    st.subheader(f"📊 현재 수집된 인원: {len(latest_df)}명")
    
    # 2. 유저 선택 필터 (사이드바)
    st.sidebar.header("검색 옵션")
    
    # 닉네임 목록 가져오기 (가나다순 정렬)
    all_users = sorted(df['nickname'].unique())
    
    # 기본적으로 상위 5명을 선택해둠
    default_users = latest_df['nickname'].head(5).tolist()
    
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