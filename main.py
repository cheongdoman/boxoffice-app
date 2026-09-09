import datetime
import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st


st.set_page_config(page_title="K-BOX OFFICE LAB", page_icon="🎬", layout="wide")

API_URL = (
    "http://kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
)
CODE_URL = (
    "http://kobis.or.kr/kobisopenapi/webservice/rest/code/searchCodeList.json"
)
KST = datetime.timezone(datetime.timedelta(hours=9))
TODAY_KST = datetime.datetime.now(KST).date()
YESTERDAY = TODAY_KST - datetime.timedelta(days=1)


st.markdown(
    """
    <style>
    .stApp {
        background:
          radial-gradient(circle at 10% 5%, rgba(239,68,68,.20), transparent 25%),
          radial-gradient(circle at 90% 15%, rgba(124,58,237,.20), transparent 28%),
          linear-gradient(135deg,#07070b,#11111b 55%,#08080e);
        color:#fff;
    }
    .block-container {max-width:1280px;padding-top:1.8rem;padding-bottom:4rem}
    #MainMenu, footer {visibility:hidden}
    .lightbar {height:5px;border-radius:20px;margin-bottom:22px;background:linear-gradient(90deg,transparent,#ef4444,#fbbf24,#fff,#8b5cf6,transparent);background-size:200% 100%;animation:move 4s linear infinite;box-shadow:0 0 24px rgba(239,68,68,.6)}
    @keyframes move {from{background-position:200% 0}to{background-position:-200% 0}}
    .hero {padding:35px 40px;border:1px solid rgba(255,255,255,.12);border-radius:28px;background:linear-gradient(120deg,rgba(239,68,68,.20),rgba(124,58,237,.16)),rgba(255,255,255,.035);box-shadow:0 22px 60px rgba(0,0,0,.4);margin-bottom:20px;animation:enter .7s ease-out}
    @keyframes enter {from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:none}}
    .eyebrow {color:#fecaca;font-size:12px;font-weight:800;letter-spacing:2px}
    .hero h1 {font-size:clamp(36px,5vw,62px);line-height:1.05;margin:8px 0;font-weight:900;letter-spacing:-3px}
    .hero h1 span {color:transparent;background:linear-gradient(90deg,#f87171,#fbbf24,#a78bfa);background-clip:text;-webkit-background-clip:text}
    .hero p {color:#c7c7d1;font-size:16px;margin:12px 0 0}
    div[data-testid="stMetric"] {min-height:125px;padding:20px;border:1px solid rgba(255,255,255,.11);border-radius:20px;background:rgba(255,255,255,.055);box-shadow:0 14px 34px rgba(0,0,0,.24);transition:.25s}
    div[data-testid="stMetric"]:hover {transform:translateY(-6px);border-color:rgba(248,113,113,.5);background:rgba(255,255,255,.085)}
    div[data-testid="stMetricValue"] {color:#fff;font-weight:900}
    .new-box {padding:18px 22px;border:1px solid rgba(59,130,246,.32);border-radius:18px;background:rgba(59,130,246,.09);margin:12px 0 18px}
    .new-title {font-size:13px;color:#93c5fd;font-weight:800;letter-spacing:1px}
    .new-list {font-size:19px;font-weight:800;margin-top:5px;color:#fff}
    button[data-baseweb="tab"] {height:50px;font-weight:800}
    div[data-testid="stDataFrame"] {border:1px solid rgba(255,255,255,.10);border-radius:18px;overflow:hidden}
    .note {padding:13px 16px;border-left:3px solid #8b5cf6;background:rgba(139,92,246,.09);border-radius:8px;color:#d7d4e8;font-size:14px}
    </style>
    """,
    unsafe_allow_html=True,
)


try:
    API_KEY = st.secrets["KOBIS_KEY"]
except KeyError:
    st.error("KOBIS API 키를 찾을 수 없습니다.")
    st.info("로컬은 .streamlit/secrets.toml, 배포 환경은 Streamlit Secrets에 KOBIS_KEY를 등록하세요.")
    st.stop()


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_regions(key: str) -> dict[str, str]:
    """KOBIS 공통코드에서 광역 상영지역 목록을 불러온다."""
    response = requests.get(
        CODE_URL,
        params={"key": key, "comCode": "0105000000"},
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if "faultInfo" in data:
        raise ValueError(data["faultInfo"].get("message", "KOBIS 지역코드 오류"))
    regions = {item["korNm"]: item["fullCd"] for item in data.get("codes", [])}
    return {"전국": "", **regions}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_day(date_text: str, key: str, wide_area_code: str = "") -> list[dict]:
    params = {"key": key, "targetDt": date_text}
    if wide_area_code:
        params["wideAreaCd"] = wide_area_code
    response = requests.get(
        API_URL,
        params=params,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    if "faultInfo" in data:
        raise ValueError(data["faultInfo"].get("message", "KOBIS API 오류"))
    return data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])


def to_frame(movies: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(movies)
    if df.empty:
        return df
    number_cols = [
        "rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt",
        "salesAmt", "salesAcc", "salesShare",
    ]
    for col in number_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt", "showCnt", "salesAmt", "salesAcc"]:
        if col in df.columns:
            df[col] = df[col].astype(int)
    return df.sort_values("rank").reset_index(drop=True)


def rank_badge(row: pd.Series) -> str:
    if row.get("rankOldAndNew") == "NEW":
        return "🆕 NEW"
    change = int(row.get("rankInten", 0))
    if change > 0:
        return f"🔺 {change}"
    if change < 0:
        return f"🔻 {abs(change)}"
    return "―"


def transparent_layout(fig: go.Figure, height: int = 470) -> go.Figure:
    fig.update_layout(
        height=height,
        margin=dict(l=15, r=15, t=55, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(255,255,255,.02)",
        font=dict(color="#dedee8"),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig


st.markdown('<div class="lightbar"></div>', unsafe_allow_html=True)
st.markdown(
    """
    <section class="hero">
      <div class="eyebrow">KOBIS · INTERACTIVE DATA LAB</div>
      <h1>영화 흥행을<br><span>데이터로 해부하다</span></h1>
      <p>일별 순위에서 7일 흐름과 영화 간 흥행 경쟁력까지 비교합니다.</p>
    </section>
    """,
    unsafe_allow_html=True,
)

try:
    REGION_CODES = fetch_regions(API_KEY)
except (requests.RequestException, ValueError):
    REGION_CODES = {"전국": ""}
    st.warning("지역 목록을 가져오지 못해 현재 전국 데이터만 표시합니다.")

date_col, region_col = st.columns([1, 1])
with date_col:
    selected_date = st.date_input(
        "📅 분석 날짜",
        value=YESTERDAY,
        max_value=YESTERDAY,
        help="KOBIS 일별 자료는 집계가 끝난 어제 날짜까지 조회할 수 있습니다.",
    )
with region_col:
    selected_region = st.selectbox(
        "🗺️ 분석 지역",
        list(REGION_CODES.keys()),
        help="전국 또는 KOBIS가 제공하는 광역 상영지역을 선택합니다.",
    )
selected_region_code = REGION_CODES[selected_region]

try:
    with st.spinner("🎞️ 박스오피스 데이터를 불러오는 중입니다..."):
        df = to_frame(fetch_day(
            selected_date.strftime("%Y%m%d"), API_KEY, selected_region_code
        ))
except requests.RequestException:
    st.error("KOBIS 서버에 연결하지 못했습니다. 인터넷 연결을 확인하고 잠시 후 다시 시도하세요.")
    st.stop()
except ValueError as exc:
    st.error(f"KOBIS API 오류: {exc}")
    st.stop()

if df.empty:
    st.warning("선택한 날짜의 박스오피스 자료가 없습니다.")
    st.stop()


# 핵심 요약 지표
top10_audience = int(df["audiCnt"].sum())
number_one = df.iloc[0]
number_one_share = number_one["audiCnt"] / top10_audience * 100 if top10_audience else 0
new_movies = df.loc[df["rankOldAndNew"] == "NEW", "movieNm"].tolist()

c1, c2, c3 = st.columns(3)
c1.metric("👥 TOP 10 일일 관객", f"{top10_audience:,}명")
c2.metric("🥇 1위 관객 점유율", f"{number_one_share:.1f}%", help="1위 영화 관객 ÷ TOP 10 전체 관객")
c3.metric("🆕 신규 진입작", f"{len(new_movies)}편")

safe_new_names = " · ".join(html.escape(name) for name in new_movies) if new_movies else "신규 진입작 없음"
st.markdown(
    f'<div class="new-box"><div class="new-title">NEW ENTRY</div><div class="new-list">{safe_new_names}</div></div>',
    unsafe_allow_html=True,
)

overview_tab, trend_tab, compare_tab, region_tab = st.tabs([
    "📊 순위 대시보드", "📈 영화별 7일 흐름", "⚔️ 영화 VS 영화", "🗺️ 지역 VS 지역",
])


with overview_tab:
    control1, control2 = st.columns([1, 1.35])
    with control1:
        display_count = st.slider("표시할 영화 수", 1, 10, 10)
    with control2:
        sort_label = st.selectbox(
            "정렬 기준",
            ["박스오피스 순위", "일일 관객", "누적 관객", "스크린 수", "일일 매출"],
        )

    sort_map = {
        "박스오피스 순위": ("rank", True),
        "일일 관객": ("audiCnt", False),
        "누적 관객": ("audiAcc", False),
        "스크린 수": ("scrnCnt", False),
        "일일 매출": ("salesAmt", False),
    }
    sort_col, ascending = sort_map[sort_label]
    shown = df.sort_values(sort_col, ascending=ascending).head(display_count).copy()
    shown["순위 변화"] = shown.apply(rank_badge, axis=1)

    graph_col, summary_col = st.columns([1.7, 1])
    with graph_col:
        y_map = {
            "박스오피스 순위": "rank",
            "일일 관객": "audiCnt",
            "누적 관객": "audiAcc",
            "스크린 수": "scrnCnt",
            "일일 매출": "salesAmt",
        }
        graph_metric = y_map[sort_label]
        if graph_metric == "rank":
            graph_metric = "audiCnt"
        fig = px.bar(
            shown,
            x="movieNm",
            y=graph_metric,
            color=graph_metric,
            color_continuous_scale=["#7c3aed", "#ef4444", "#fbbf24"],
            labels={"movieNm": "영화명", graph_metric: sort_label if sort_label != "박스오피스 순위" else "일일 관객"},
        )
        fig.update_layout(coloraxis_showscale=False, xaxis_title="", xaxis_tickangle=-12)
        transparent_layout(fig)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with summary_col:
        share_fig = go.Figure(go.Pie(
            labels=df["movieNm"], values=df["audiCnt"], hole=.64,
            marker_colors=["#ef4444", "#f59e0b", "#8b5cf6", "#3b82f6", "#10b981", "#ec4899", "#14b8a6", "#6366f1", "#f97316", "#64748b"],
            textinfo="percent",
        ))
        share_fig.add_annotation(text=f"<b>{number_one_share:.1f}%</b><br>1위 점유율", x=.5, y=.5, showarrow=False, font=dict(size=18, color="white"))
        share_fig.update_layout(title="TOP 10 관객 점유율", showlegend=False)
        transparent_layout(share_fig)
        st.plotly_chart(share_fig, use_container_width=True, config={"displayModeBar": False})

    table = shown[["rank", "movieNm", "순위 변화", "audiCnt", "audiAcc", "scrnCnt", "salesAmt"]].copy()
    table.columns = ["순위", "영화명", "순위 변화", "일일 관객", "누적 관객", "스크린", "일일 매출"]
    st.dataframe(
        table,
        hide_index=True,
        use_container_width=True,
        column_config={
            "일일 관객": st.column_config.NumberColumn(format="%,d명"),
            "누적 관객": st.column_config.NumberColumn(format="%,d명"),
            "스크린": st.column_config.NumberColumn(format="%,d개"),
            "일일 매출": st.column_config.NumberColumn(format="%,d원"),
        },
    )


with trend_tab:
    st.subheader("선택한 영화의 최근 7일 흥행 흐름")
    selected_movie = st.selectbox(
        "선택 날짜 TOP 10에서 영화를 고르세요",
        df["movieNm"].tolist(),
        key="trend_movie",
    )

    history_rows = []
    history_dates = [selected_date - datetime.timedelta(days=i) for i in range(6, -1, -1)]
    try:
        with st.spinner("7일 데이터를 모으는 중입니다..."):
            for day in history_dates:
                day_movies = fetch_day(
                    day.strftime("%Y%m%d"), API_KEY, selected_region_code
                )
                match = next((m for m in day_movies if m["movieNm"] == selected_movie), None)
                history_rows.append({
                    "날짜": day,
                    "일일 관객": int(match["audiCnt"]) if match else None,
                    "순위": int(match["rank"]) if match else None,
                })
    except requests.RequestException:
        st.error("7일 데이터를 가져오는 중 연결 오류가 발생했습니다.")
        st.stop()

    history = pd.DataFrame(history_rows)
    audience_fig = px.area(
        history, x="날짜", y="일일 관객", markers=True,
        title=f"{selected_movie} · 일일 관객 흐름",
        color_discrete_sequence=["#ef4444"],
    )
    transparent_layout(audience_fig, 400)
    audience_fig.update_traces(line=dict(width=3), fillcolor="rgba(239,68,68,.16)")

    rank_fig = px.line(
        history, x="날짜", y="순위", markers=True,
        title=f"{selected_movie} · 순위 흐름",
        color_discrete_sequence=["#fbbf24"],
    )
    transparent_layout(rank_fig, 400)
    rank_fig.update_traces(line=dict(width=3), marker=dict(size=10))
    rank_fig.update_yaxes(autorange="reversed", dtick=1, range=[10.5, .5])

    t1, t2 = st.columns(2)
    t1.plotly_chart(audience_fig, use_container_width=True, config={"displayModeBar": False})
    t2.plotly_chart(rank_fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('<div class="note">KOBIS 일별 API는 TOP 10만 제공합니다. 영화가 TOP 10 밖이었던 날은 선이 비어 보이며, 관객이 0명이라는 뜻은 아닙니다.</div>', unsafe_allow_html=True)


with compare_tab:
    st.subheader("두 작품의 흥행 경쟁력 비교")
    movie_names = df["movieNm"].tolist()
    pick1, pick2 = st.columns(2)
    movie_a = pick1.selectbox("영화 A", movie_names, index=0)
    movie_b = pick2.selectbox("영화 B", movie_names, index=1 if len(movie_names) > 1 else 0)

    if movie_a == movie_b:
        st.warning("서로 다른 두 영화를 선택하세요.")
    else:
        raw_metrics = ["audiCnt", "audiAcc", "scrnCnt", "salesAmt"]
        labels = ["일일 관객", "누적 관객", "스크린", "일일 매출", "랭킹 파워"]
        max_values = {metric: max(float(df[metric].max()), 1) for metric in raw_metrics}

        def radar_values(movie_name: str) -> tuple[list[float], pd.Series]:
            row = df.loc[df["movieNm"] == movie_name].iloc[0]
            values = [float(row[m]) / max_values[m] * 100 for m in raw_metrics]
            values.append((11 - int(row["rank"])) / 10 * 100)
            return values, row

        values_a, row_a = radar_values(movie_a)
        values_b, row_b = radar_values(movie_b)
        radar = go.Figure()
        radar.add_trace(go.Scatterpolar(r=values_a + [values_a[0]], theta=labels + [labels[0]], fill="toself", name=movie_a, line_color="#ef4444", fillcolor="rgba(239,68,68,.20)"))
        radar.add_trace(go.Scatterpolar(r=values_b + [values_b[0]], theta=labels + [labels[0]], fill="toself", name=movie_b, line_color="#8b5cf6", fillcolor="rgba(139,92,246,.20)"))
        radar.update_layout(
            polar=dict(bgcolor="rgba(255,255,255,.02)", radialaxis=dict(visible=True, range=[0, 100], gridcolor="rgba(255,255,255,.15)"), angularaxis=dict(gridcolor="rgba(255,255,255,.12)")),
            title="상대 경쟁력 레이더 (TOP 10 내 최고값 = 100)",
        )
        transparent_layout(radar, 560)
        st.plotly_chart(radar, use_container_width=True, config={"displayModeBar": False})

        comparison = pd.DataFrame({
            "지표": ["순위", "일일 관객", "누적 관객", "스크린", "일일 매출", "랭킹 파워"],
            movie_a: [int(row_a["rank"]), int(row_a["audiCnt"]), int(row_a["audiAcc"]), int(row_a["scrnCnt"]), int(row_a["salesAmt"]), round(values_a[-1], 1)],
            movie_b: [int(row_b["rank"]), int(row_b["audiCnt"]), int(row_b["audiAcc"]), int(row_b["scrnCnt"]), int(row_b["salesAmt"]), round(values_b[-1], 1)],
        })
        st.dataframe(comparison, hide_index=True, use_container_width=True)
        st.markdown('<div class="note">레이더 점수는 선택 날짜 TOP 10 안에서 각 지표의 최고값을 100으로 환산한 상대 점수입니다. 랭킹 파워는 1위 100점, 10위 10점입니다.</div>', unsafe_allow_html=True)


with region_tab:
    st.subheader("지역 A VS 지역 B")
    st.write("전국을 포함한 두 지역을 직접 골라 영화 관람 특징을 비교합니다.")

    region_names = list(REGION_CODES.keys())
    if len(region_names) < 2:
        st.warning("KOBIS 지역코드를 불러오지 못해 지역 비교를 사용할 수 없습니다.")
    else:
        default_b = region_names.index(selected_region) if selected_region in region_names and selected_region != "전국" else 1
        select_a, select_b = st.columns(2)
        region_a = select_a.selectbox("🅰️ 지역 A", region_names, index=0, key="region_a")
        region_b = select_b.selectbox("🅱️ 지역 B", region_names, index=default_b, key="region_b")

        if region_a == region_b:
            st.warning("서로 다른 두 지역을 선택하세요.")
        else:
            try:
                with st.spinner(f"{region_a}과 {region_b} 데이터를 비교하는 중입니다..."):
                    df_a = to_frame(fetch_day(
                        selected_date.strftime("%Y%m%d"), API_KEY, REGION_CODES[region_a]
                    ))
                    df_b = to_frame(fetch_day(
                        selected_date.strftime("%Y%m%d"), API_KEY, REGION_CODES[region_b]
                    ))
            except requests.RequestException:
                st.error("지역 비교 데이터를 가져오는 중 연결 오류가 발생했습니다.")
                st.stop()
            except ValueError as exc:
                st.error(f"KOBIS API 오류: {exc}")
                st.stop()

            if df_a.empty or df_b.empty:
                st.warning("두 지역 중 한 곳 이상의 박스오피스 자료가 없습니다.")
            else:
                total_a = int(df_a["audiCnt"].sum())
                total_b = int(df_b["audiCnt"].sum())
                share_a = df_a.iloc[0]["audiCnt"] / total_a * 100 if total_a else 0
                share_b = df_b.iloc[0]["audiCnt"] / total_b * 100 if total_b else 0
                common_count = len(set(df_a["movieCd"]) & set(df_b["movieCd"]))

                r1, r2, r3, r4 = st.columns(4)
                r1.metric(f"{region_a} TOP 10 관객", f"{total_a:,}명")
                r2.metric(f"{region_b} TOP 10 관객", f"{total_b:,}명")
                r3.metric(f"{region_a} 1위 집중도", f"{share_a:.1f}%")
                r4.metric(
                    f"{region_b} 1위 집중도",
                    f"{share_b:.1f}%",
                    delta=f"{region_a} 대비 {share_b - share_a:+.1f}%p",
                )

                safe_winner_a = html.escape(str(df_a.iloc[0]["movieNm"]))
                safe_winner_b = html.escape(str(df_b.iloc[0]["movieNm"]))
                st.markdown(
                    f'<div class="new-box"><div class="new-title">REGIONAL MATCH</div>'
                    f'<div class="new-list">🅰️ {region_a} 1위 · {safe_winner_a}<br>'
                    f'🅱️ {region_b} 1위 · {safe_winner_b}<br>'
                    f'🎞️ 두 지역 공통 TOP 10 · {common_count}편</div></div>',
                    unsafe_allow_html=True,
                )

                plot_a = df_a[["movieCd", "movieNm", "audiCnt"]].copy()
                plot_a["지역"] = region_a
                plot_a["관객 점유율"] = plot_a["audiCnt"] / total_a * 100
                plot_b = df_b[["movieCd", "movieNm", "audiCnt"]].copy()
                plot_b["지역"] = region_b
                plot_b["관객 점유율"] = plot_b["audiCnt"] / total_b * 100
                comparison_plot = pd.concat([plot_a, plot_b], ignore_index=True)

                share_bar = px.bar(
                    comparison_plot,
                    x="movieNm",
                    y="관객 점유율",
                    color="지역",
                    barmode="group",
                    color_discrete_map={region_a: "#ef4444", region_b: "#8b5cf6"},
                    labels={"movieNm": "영화명"},
                    title=f"{region_a} VS {region_b} · TOP 10 내 관객 점유율",
                )
                share_bar.update_layout(xaxis_title="", xaxis_tickangle=-15)
                share_bar.update_yaxes(ticksuffix="%")
                transparent_layout(share_bar, 500)
                st.plotly_chart(
                    share_bar, use_container_width=True,
                    config={"displayModeBar": False},
                )

                table_a = df_a[["movieCd", "movieNm", "rank", "audiCnt", "salesAmt"]].rename(
                    columns={
                        "movieNm": "영화명 A",
                        "rank": f"{region_a} 순위",
                        "audiCnt": f"{region_a} 관객",
                        "salesAmt": f"{region_a} 매출",
                    }
                )
                table_b = df_b[["movieCd", "movieNm", "rank", "audiCnt", "salesAmt"]].rename(
                    columns={
                        "movieNm": "영화명 B",
                        "rank": f"{region_b} 순위",
                        "audiCnt": f"{region_b} 관객",
                        "salesAmt": f"{region_b} 매출",
                    }
                )
                rank_table = table_a.merge(table_b, on="movieCd", how="outer")
                rank_table["영화명"] = rank_table["영화명 A"].fillna(rank_table["영화명 B"])
                rank_table = rank_table[[
                    "영화명", f"{region_a} 순위", f"{region_b} 순위",
                    f"{region_a} 관객", f"{region_b} 관객",
                    f"{region_a} 매출", f"{region_b} 매출",
                ]].sort_values([f"{region_a} 순위", f"{region_b} 순위"], na_position="last")
                st.dataframe(
                    rank_table,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        f"{region_a} 관객": st.column_config.NumberColumn(format="%,d명"),
                        f"{region_b} 관객": st.column_config.NumberColumn(format="%,d명"),
                        f"{region_a} 매출": st.column_config.NumberColumn(format="%,d원"),
                        f"{region_b} 매출": st.column_config.NumberColumn(format="%,d원"),
                    },
                )
                st.markdown(
                    '<div class="note">두 지역은 인구와 영화관 수가 다르므로 전체 관객 수만으로 선호도를 판단하면 안 됩니다. 영화별 관객 점유율과 순위 차이를 함께 살펴보세요.</div>',
                    unsafe_allow_html=True,
                )


st.caption(f"자료: 영화진흥위원회 KOBIS · 기준일: {selected_date} · 분석 지역: {selected_region}")
