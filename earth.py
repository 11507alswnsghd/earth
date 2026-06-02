import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# --- 1. 페이지 대시보드 스타일 설정 ---
st.set_page_config(
    page_title="EARTHQUAKE RISK MONITOR v2",
    page_icon="🌍",
    layout="wide",  
)

# --- 2. 안전한 데이터 로드 시스템 (순수 CSV 버전) ---
@st.cache_data  
def load_data():
    encodings = ['utf-8', 'cp949', 'utf-8-sig']
    for enc in encodings:
        try:
            # 💡 zip 대신 다시 earth.csv를 직접 읽도록 원상복구했습니다.
            return pd.read_csv("earth.csv", encoding=enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return None

df_new = load_data()

# --- 3. 글로벌 설정 및 테마 컬러 매핑 ---
risk_dict = {0: '⚠️ 고위험 (HIGH)', 1: '✅ 안정 (LOW)', 2: '🟡 주의 (🚨 MEDIUM)'}
colors = {0: '#FF3333', 1: '#33FF57', 2: '#FFAF33'} 

# --- 4. 컨트롤 패널 (사이드바 메뉴) ---
st.sidebar.markdown("## 📡 SYSTEM CONTROL")
st.sidebar.markdown("---")
st.sidebar.subheader("📍 TARGET COORDINATES")

lat = st.sidebar.number_input("LATITUDE (위도)", value=37.5665, format="%.4f")
lon = st.sidebar.number_input("LONGITUDE (경도)", value=126.9780, format="%.4f")
radius = st.sidebar.slider("ANALYSIS RADIUS (분석 반경도)", 1.0, 10.0, 5.0, step=0.5)
st.sidebar.markdown("---")

# --- 5. 데이터 검증 및 지능형 'cluster' 열 매칭 ---
if df_new is None:
    # 💡 에러 메시지도 CSV 기준으로 명확하게 변경했습니다.
    st.error("❌ 'earth.csv' 파일을 읽는 데 실패했습니다. 파일이 C:\\streamlit\\ 폴더 안에 있는지 확인해주세요.")
else:
    cluster_col = None
    
    for col in df_new.columns:
        if str(col).lower() == 'cluster':
            cluster_col = col
            break
            
    if cluster_col is None:
        for col in reversed(df_new.columns):
            if col not in ['위도', '경도'] and pd.api.types.is_numeric_dtype(df_new[col]):
                try:
                    first_val = df_new[col].dropna().iloc[0]
                    float(first_val)
                    cluster_col = col
                    break
                except (ValueError, IndexError):
                    continue

    if cluster_col is None:
        df_new['tmp_cluster'] = 1
        cluster_col = 'tmp_cluster'

    st.sidebar.caption("System Status: ONLINE")
    st.sidebar.caption(f"📊 Total Dataset: {len(df_new):,} rows")
    st.sidebar.caption(f"🔍 Active Cluster Column: '{cluster_col}'")

    # --- 6. 메인 대시보드 헤더 ---
    st.markdown("<h1 style='text-align: center; color: #E0E0E0;'>📊 EARTHQUAKE RISK MONITOR v2</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #888888;'>실시간 지진 데이터 분석 및 군집 기반 위험도 예측 시스템</p>", unsafe_allow_html=True)
    st.markdown("---")

    # --- 7. 위험도 분석 및 메트릭 레이아웃 연산 ---
    near_df = df_new[
        (df_new['위도'] >= lat - radius) & (df_new['위도'] <= lat + radius) & 
        (df_new['경도'] >= lon - radius) & (df_new['경도'] <= lon + radius)
    ]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(label="🎯 TARGET LAT / LON", value=f"{lat} / {lon}")
    with col2:
        st.metric(label="🗂️ NEIGHBOR DATA COUNT", value=f"{len(near_df)}개")

    if not near_df.empty:
        cluster_ratio = near_df[cluster_col].value_counts(normalize=True)
        raw_main = cluster_ratio.idxmax()
        
        try:
            main_cluster = int(float(raw_main))
        except ValueError:
            main_cluster = 1 
            
        risk_level = risk_dict.get(main_cluster, '🟡 주의 (🚨 MEDIUM)')
        
        with col3:
            st.metric(label="🚨 SYSTEM RISK LEVEL", value=risk_level)
        
        st.markdown("### 🔍 ANALYSIS REPORT")
        if main_cluster == 0:
            st.error(f"**[위험]** 해당 지역 주변 데이터 분석 결과, 과거 지진 집중 군집(Cluster {main_cluster})에 속해 있어 위험도가 매우 높습니다.")
        elif main_cluster == 2:
            st.warning(f"**[주의]** 중간 수준의 지진 활동이 감지되는 구역입니다. 지속적인 모니터링이 필요합니다.")
        else:
            st.success(f"**[안전]** 지진 발생 빈도가 낮은 안전 군집 구역입니다.")
    else:
        with col3:
            st.metric(label="🚨 SYSTEM RISK LEVEL", value="데이터 부족", delta="N/A")
        st.info("💡 선택하신 분석 반경 내에 참고할 수 있는 기존 지진 데이터가 존재하지 않습니다.")

    st.markdown("---")

    # --- 8. 다크 테마 기반 지도 시각화 (1,000개 경량화 적용) ---
    st.markdown("### 🗺️ GLOBAL ACTIVITY & DENSITY MAP (Top 1,000 Samples)")

    m = folium.Map(location=[lat, lon], zoom_start=5, tiles='CartoDB dark_matter')

    # 지도 렉 방지를 위해 가볍게 1000개만 랜덤 샘플링해서 화면에 띄웁니다.
    df_sample = df_new.sample(n=min(1000, len(df_new)), random_state=42)

    for _, row in df_sample.iterrows():
        try:
            c_val = int(float(row[cluster_col])) if pd.notnull(row[cluster_col]) else 1
        except ValueError:
            c_val = 1
            
        folium.CircleMarker(
            location=[row['위도'], row['경도']], 
            radius=1.5,
            color=colors.get(c_val, '#FFFFFF'),
            fill=True,
            fill_opacity=0.4
        ).add_to(m)

    folium.Circle(
        location=[lat, lon],
        radius=radius * 111000, 
        color="#FFFFFF",
        weight=1,
        fill=True,
        fill_color="#FFFFFF",
        fill_opacity=0.06,
        dash_array='5, 5'
    ).add_to(m)

    folium.Marker(
        location=[lat, lon],
        popup=f"Target: {lat}, {lon}",
        icon=folium.Icon(color='blue', icon='bullseye', prefix='fa')
    ).add_to(m)

    st_folium(m, width="100%", height=600)