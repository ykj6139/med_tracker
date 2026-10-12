import streamlit as st
import pandas as pd
from datetime import datetime, date

st.set_page_config(page_title="구급의약품 유효기간 관리 시스템", page_icon="💊", layout="wide")

st.title("💊 119구급대 의약품 유효기간 모니터링 시스템")
st.markdown("구급차량 및 보관고 내 의약품의 유효기간을 실시간 계산하여 교체 및 재신청 대상 품목을 안내합니다.")

# 1. 샘플 데이터 생성 및 템플릿 다운로드
@st.cache_data
def get_sample_data():
    today = date.today()
    return pd.DataFrame({
        "품목명": ["에피네프린", "아미오다론", "포도당 50%", "생리식염수 500ml", "아트로핀", "마그네슘"],
        "규격": ["1mg/1ml", "150mg/3ml", "100ml", "500ml", "0.5mg/1ml", "10% 20ml"],
        "보관위치": ["구급차 1호", "구급차 1호", "구급차 2호", "약품보관고", "구급차 1호", "구급차 2호"],
        "수량": [5, 4, 3, 20, 6, 2],
        "유효기간": [
            (today + pd.Timedelta(days=-5)).strftime("%Y-%m-%d"),   # 이미 만료
            (today + pd.Timedelta(days=8)).strftime("%Y-%m-%d"),    # 긴급 교체 (14일 이내)
            (today + pd.Timedelta(days=22)).strftime("%Y-%m-%d"),   # 재신청 주의 (30일 이내)
            (today + pd.Timedelta(days=120)).strftime("%Y-%m-%d"),  # 정상
            (today + pd.Timedelta(days=3)).strftime("%Y-%m-%d"),    # 긴급 교체
            (today + pd.Timedelta(days=200)).strftime("%Y-%m-%d")   # 정상
        ]
    })

# 사이드바: 파일 업로드 및 템플릿
with st.sidebar:
    st.header("📋 데이터 관리")
    sample_df = get_sample_data()
    csv_template = sample_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("엑셀/CSV 양식 다운로드", csv_template, "구급의약품_관리양식.csv", "text/csv")
    
    st.markdown("---")
    uploaded_file = st.file_uploader("의약품 목록 파일 업로드 (CSV/XLSX)", type=["csv", "xlsx"])

# 데이터 로드
if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file)
    else:
        df = pd.read_excel(uploaded_file)
else:
    df = sample_df.copy()

# 2. D-Day 및 상태 판정 계산
today = date.today()
df['유효기간'] = pd.to_datetime(df['유효기간']).dt.date
df['남은일수'] = (df['유효기간'] - today).apply(lambda x: x.days)

def classify_status(days):
    if days < 0:
        return "🔴 유효기간 만료"
    elif days <= 14:
        return "🟠 교체 긴급 (D-14)"
    elif days <= 30:
        return "🟡 신청 주의 (D-30)"
    else:
        return "🟢 정상 보관"

df['관리상태'] = df['남은일수'].apply(classify_status)

# 3. 상단 대시보드 요약 지표
expired_count = len(df[df['남은일수'] < 0])
urgent_count = len(df[(df['남은일수'] >= 0) & (df['남은일수'] <= 14)])
warning_count = len(df[(df['남은일수'] > 14) & (df['남은일수'] <= 30)])
normal_count = len(df[df['남은일수'] > 30])

col1, col2, col3, col4 = st.columns(4)
col1.metric("🔴 폐기 대상 (만료)", f"{expired_count} 건")
col2.metric("🟠 긴급 교체 (14일 이내)", f"{urgent_count} 건")
col3.metric("🟡 신청 준비 (30일 이내)", f"{warning_count} 건")
col4.metric("🟢 정상 보관", f"{normal_count} 건")

st.markdown("---")

# 4. 즉시 조치 필요 품목 알림 배너
action_needed = df[df['남은일수'] <= 14]
if not action_needed.empty:
    st.error(f"🚨 **즉시 조치 필요:** 유효기간이 지났거나 14일 이내 만료 예정인 약품이 총 {len(action_needed)}건 있습니다.")
    st.dataframe(
        action_needed[['관리상태', '보관위치', '품목명', '규격', '수량', '유효기간', '남은일수']],
        use_container_width=True
    )

# 5. 전체 품목 조회 및 위치별 필터링
st.subheader("📦 전체 의약품 현황 목록")

filter_col1, filter_col2 = st.columns(2)
with filter_col1:
    locations = ["전체"] + list(df['보관위치'].unique())
    selected_loc = st.selectbox("보관위치 필터", locations)
with filter_col2:
    status_options = ["전체", "조치 필요(만료/긴급/주의)", "정상 보관"]
    selected_status = st.selectbox("상태 필터", status_options)

view_df = df.copy()
if selected_loc != "전체":
    view_df = view_df[view_df['보관위치'] == selected_loc]

if selected_status == "조치 필요(만료/긴급/주의)":
    view_df = view_df[view_df['남은일수'] <= 30]
elif selected_status == "정상 보관":
    view_df = view_df[view_df['남은일수'] > 30]

# 남은 일수 오름차순 정렬 (임박한 약품이 가장 위에 오도록)
view_df = view_df.sort_values(by="남은일수")

st.dataframe(
    view_df[['관리상태', '보관위치', '품목명', '규격', '수량', '유효기간', '남은일수']],
    use_container_width=True
)

# 6. 교체/신청 대상 엑셀 다운로드 (보고 및 조달용)
st.subheader("📑 조달 및 교체 명단 추출")
reorder_df = df[df['남은일수'] <= 30].sort_values(by="남은일수")
if not reorder_df.empty:
    reorder_csv = reorder_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="교체·재신청 대상 품목 다운로드(CSV)",
        data=reorder_csv,
        file_name=f"구급의약품_교체신청목록_{today.strftime('%Y%m%d')}.csv",
        mime="text/csv"
    )
else:
    st.info("현재 30일 이내에 만료되는 품목이 없습니다.")