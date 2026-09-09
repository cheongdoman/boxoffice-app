# KOBIS 일별 박스오피스 API를 이용한 Streamlit 웹앱

import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# 웹페이지 기본 설정
st.set_page_config(
    page_title="박스오피스 분석",
    page_icon="🎬",
    layout="wide"
)

# KOBIS 일별 박스오피스 API 주소
API_URL = (
    "http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
)

# 한국 시간 설정
KST = datetime.timezone(datetime.timedelta(hours=9))
today_kst = datetime.datetime.now(KST).date()
yesterday = today_kst - datetime.timedelta(days=1)


# Streamlit Secrets에 저장한 API 키 가져오기
try:
    api_key = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error("KOBIS API 키를 찾을 수 없습니다.")
    st.info(
        "로컬에서는 .streamlit/secrets.toml 파일에, "
        "배포 후에는 Streamlit의 Secrets에 KOBIS_KEY를 등록하세요."
    )
    st.stop()


@st.cache_data(ttl=3600)
def fetch_boxoffice(date_text, key):
    """선택한 날짜의 박스오피스 데이터를 KOBIS에서 받아온다."""

    params = {
        "key": key,
        "targetDt": date_text
    }

    response = requests.get(
        API_URL,
        params=params,
        timeout=15
    )

    # 인터넷 연결 또는 서버 요청 오류 확인
    response.raise_for_status()

    return response.json()


# 페이지 제목
st.title("🎬 일별 박스오피스 분석")
st.write("영화진흥위원회 KOBIS의 공식 데이터를 이용합니다.")

# 오늘 자료는 아직 집계되지 않았으므로 어제까지만 선택 가능
selected_date = st.date_input(
    "박스오피스를 조회할 날짜를 선택하세요.",
    value=yesterday,
    max_value=yesterday
)

target_date = selected_date.strftime("%Y%m%d")

# API 호출
try:
    data = fetch_boxoffice(target_date, api_key)

except requests.exceptions.Timeout:
    st.error("KOBIS 서버의 응답 시간이 초과되었습니다.")
    st.info("잠시 후 다시 시도해 주세요.")
    st.stop()

except requests.exceptions.RequestException as error:
    st.error("KOBIS 서버에 연결하지 못했습니다.")
    st.write(error)
    st.stop()

except ValueError:
    st.error("서버가 올바른 JSON 데이터를 보내지 않았습니다.")
    st.stop()


# API 키 오류 등 확인
if "faultInfo" in data:
    message = data["faultInfo"].get(
        "message",
        "알 수 없는 API 오류가 발생했습니다."
    )

    st.error(f"KOBIS API 오류: {message}")
    st.info("Streamlit Secrets에 저장한 KOBIS_KEY를 확인하세요.")
    st.stop()


# JSON 내부에서 영화 목록 꺼내기
movies = (
    data
    .get("boxOfficeResult", {})
    .get("dailyBoxOfficeList", [])
)

if not movies:
    st.warning("해당 날짜의 박스오피스 자료가 없습니다.")
    st.info("오늘이 아닌, 집계가 완료된 이전 날짜를 선택해 주세요.")
    st.stop()


# JSON 목록을 표 형태의 데이터프레임으로 변환
df = pd.DataFrame(movies)

# API가 숫자를 문자열로 보내므로 숫자 자료형으로 변환
number_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
    "showCnt",
    "salesAmt"
]

for column in number_columns:
    df[column] = pd.to_numeric(
        df[column],
        errors="coerce"
    ).fillna(0).astype(int)


# 순위 변화 표시 함수
def make_rank_change(value):
    if value > 0:
        return f"🔺 {value}"
    elif value < 0:
        return f"🔻 {abs(value)}"
    else:
        return "—"


df["rankChangeText"] = df["rankInten"].apply(make_rank_change)

# 누적 관객 100만 명 이상이면 트로피 표시
df["movieDisplay"] = df.apply(
    lambda row: (
        f"🏆 {row['movieNm']}"
        if row["audiAcc"] >= 1_000_000
        else row["movieNm"]
    ),
    axis=1
)

# 순위대로 정렬
df = df.sort_values("rank")


# 1위 영화 표시
top_movie = df.iloc[0]

st.subheader(f"🥇 1위: {top_movie['movieNm']}")

column1, column2, column3 = st.columns(3)

column1.metric(
    "당일 관객 수",
    f"{top_movie['audiCnt']:,}명"
)

column2.metric(
    "누적 관객 수",
    f"{top_movie['audiAcc']:,}명"
)

column3.metric(
    "스크린 수",
    f"{top_movie['scrnCnt']:,}개"
)


# 전체 순위표 만들기
st.subheader(f"📋 {selected_date} 박스오피스 순위")

table = df[
    [
        "rank",
        "movieDisplay",
        "rankChangeText",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
        "showCnt"
    ]
].copy()

table.columns = [
    "순위",
    "영화명",
    "순위 변화",
    "개봉일",
    "당일 관객 수",
    "누적 관객 수",
    "스크린 수",
    "상영 횟수"
]

st.dataframe(
    table.style.format({
        "당일 관객 수": "{:,}",
        "누적 관객 수": "{:,}",
        "스크린 수": "{:,}",
        "상영 횟수": "{:,}"
    }),
    hide_index=True,
    use_container_width=True
)

st.caption(
    "🔺 순위 상승 · 🔻 순위 하락 · "
    "🏆 누적 관객 100만 명 이상"
)


# 관객 수 상위 5편 그래프
st.subheader("📊 당일 관객 수 상위 5편")

top5 = (
    df
    .sort_values("audiCnt", ascending=False)
    .head(5)
)

chart = px.bar(
    top5,
    x="movieNm",
    y="audiCnt",
    color="audiCnt",
    text="audiCnt",
    labels={
        "movieNm": "영화명",
        "audiCnt": "당일 관객 수"
    }
)

chart.update_traces(
    texttemplate="%{text:,}명",
    textposition="outside"
)

chart.update_layout(
    coloraxis_showscale=False,
    xaxis_title="영화명",
    yaxis_title="관객 수"
)

st.plotly_chart(
    chart,
    use_container_width=True
)


# 간단한 자동 분석
total_audience = df["audiCnt"].sum()
top5_audience = top5["audiCnt"].sum()
top5_share = top5_audience / total_audience * 100

st.subheader("🔍 데이터 분석 결과")

st.write(
    f"선택한 날짜의 박스오피스 1위는 "
    f"**{top_movie['movieNm']}**입니다."
)

st.write(
    f"1위 영화의 당일 관객 수는 "
    f"**{top_movie['audiCnt']:,}명**이고, "
    f"누적 관객 수는 **{top_movie['audiAcc']:,}명**입니다."
)

st.write(
    f"상위 5개 영화가 상위 10개 영화 관객 수에서 차지하는 비율은 "
    f"**{top5_share:.1f}%**입니다."
)