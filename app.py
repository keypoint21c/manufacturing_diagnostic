import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="제조기업 경영진단", layout="wide")
st.title("🏭 제조기업 경영진단 (실전 버전)")
st.caption("엑셀/CSV 업로드 → 컬럼 매핑 → KPI 산출 → 점수/리스크 신호등 → 개선 포인트 제시")

uploaded = st.file_uploader("📤 생산/재무/품질 데이터(엑셀 또는 CSV) 업로드", type=["xlsx", "csv"])

def load_df(file):
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

def to_num(s):
    return pd.to_numeric(s, errors="coerce")

def safe_sum(df, col):
    if col == "(없음)":
        return None
    return float(to_num(df[col]).fillna(0).sum())

def safe_mean(df, col):
    if col == "(없음)":
        return None
    x = to_num(df[col]).dropna()
    return None if x.empty else float(x.mean())

def safe_ratio(n, d):
    if n is None or d in [None, 0]:
        return None
    return n / d

def score_by_threshold(value, good, warn):
    """
    value가 높을수록 좋은 지표(예: 이익률):
      - value >= good  -> 100
      - warn <= value < good -> 70
      - value < warn -> 40
    """
    if value is None:
        return None
    if value >= good:
        return 100
    if value >= warn:
        return 70
    return 40

def score_by_inverse_threshold(value, good, warn):
    """
    value가 낮을수록 좋은 지표(예: 불량률, 리드타임):
      - value <= good -> 100
      - good < value <= warn -> 70
      - value > warn -> 40
    """
    if value is None:
        return None
    if value <= good:
        return 100
    if value <= warn:
        return 70
    return 40

def traffic_light(score):
    if score is None:
        return "⚪"
    if score >= 85:
        return "🟢"
    if score >= 60:
        return "🟠"
    return "🔴"

if not uploaded:
    st.info("업로드 후 시작됩니다. (권장 컬럼 예: 매출, 매출원가, 고정비, 인건비, 생산수량, 양품수량, 불량수량, 납기일, 출고일, 재고수량 등)")
    st.stop()

df = load_df(uploaded)
st.subheader("1) 데이터 미리보기")
st.dataframe(df.head(50), use_container_width=True)

cols = df.columns.tolist()

st.subheader("2) 컬럼 매핑 (파일마다 이름이 달라도 선택하면 됩니다)")
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    col_date = st.selectbox("기준일(선택)", ["(없음)"] + cols)
with c2:
    col_sales = st.selectbox("매출", ["(없음)"] + cols)
with c3:
    col_cogs = st.selectbox("매출원가", ["(없음)"] + cols)
with c4:
    col_fixed = st.selectbox("고정비", ["(없음)"] + cols)
with c5:
    col_labor = st.selectbox("인건비", ["(없음)"] + cols)

c6, c7, c8, c9, c10 = st.columns(5)
with c6:
    col_prod_qty = st.selectbox("생산수량", ["(없음)"] + cols)
with c7:
    col_good_qty = st.selectbox("양품수량", ["(없음)"] + cols)
with c8:
    col_defect_qty = st.selectbox("불량수량", ["(없음)"] + cols)
with c9:
    col_due = st.selectbox("납기일(선택)", ["(없음)"] + cols)
with c10:
    col_ship = st.selectbox("출고/완료일(선택)", ["(없음)"] + cols)

c11, c12, c13, c14, c15 = st.columns(5)
with c11:
    col_inventory = st.selectbox("재고수량(선택)", ["(없음)"] + cols)
with c12:
    col_unit_cost = st.selectbox("단위원가(선택)", ["(없음)"] + cols)
with c13:
    col_unit_price = st.selectbox("단가(선택)", ["(없음)"] + cols)
with c14:
    col_overtime = st.selectbox("연장근로시간(선택)", ["(없음)"] + cols)
with c15:
    col_downtime = st.selectbox("비가동시간(선택)", ["(없음)"] + cols)

st.divider()

# ---- KPI 계산 ----
sales = safe_sum(df, col_sales)
cogs = safe_sum(df, col_cogs)
fixed = safe_sum(df, col_fixed)
labor = safe_sum(df, col_labor)

gross = None if (sales is None or cogs is None) else (sales - cogs)
gross_margin = safe_ratio(gross, sales)

op_profit = None
if sales is not None:
    op_profit = sales
    if cogs is not None: op_profit -= cogs
    if fixed is not None: op_profit -= fixed
    if labor is not None: op_profit -= labor

op_margin = safe_ratio(op_profit, sales)

prod_qty = safe_sum(df, col_prod_qty)
good_qty = safe_sum(df, col_good_qty)
defect_qty = safe_sum(df, col_defect_qty)

# 불량률 = 불량 / 생산
defect_rate = safe_ratio(defect_qty, prod_qty)

# 수율 = 양품 / 생산
yield_rate = safe_ratio(good_qty, prod_qty)

# 납기 준수율(간이): 출고일 <= 납기일
on_time_rate = None
if col_due != "(없음)" and col_ship != "(없음)":
    due = pd.to_datetime(df[col_due], errors="coerce")
    ship = pd.to_datetime(df[col_ship], errors="coerce")
    valid = due.notna() & ship.notna()
    if valid.any():
        on_time_rate = float((ship[valid] <= due[valid]).mean())

# 재고금액(간이): 재고수량 * 단위원가
inventory_value = None
if col_inventory != "(없음)" and col_unit_cost != "(없음)":
    inv = to_num(df[col_inventory]).fillna(0)
    uc = to_num(df[col_unit_cost]).fillna(0)
    inventory_value = float((inv * uc).sum())

# ---- 점수화(룰 기반) ----
# 대표님 현장용 기본 기준치(업종별로 조정 가능)
score_gm = score_by_threshold(gross_margin, good=0.25, warn=0.15)          # 총이익률 25%↑ 좋음, 15% 미만 위험
score_om = score_by_threshold(op_margin, good=0.10, warn=0.05)             # 영업이익률 10%↑ 좋음, 5% 미만 위험
score_def = score_by_inverse_threshold(defect_rate, good=0.01, warn=0.03)  # 불량률 1% 이하 좋음, 3% 초과 위험
score_yield = score_by_threshold(yield_rate, good=0.98, warn=0.95)         # 수율 98%↑ 좋음, 95% 미만 위험
score_otd = score_by_threshold(on_time_rate, good=0.95, warn=0.90)         # 납기 95%↑ 좋음, 90% 미만 위험

# 재고는 업종편차 커서 "재고금액/매출"로 간이 판단 (데이터 있으면)
inv_to_sales = safe_ratio(inventory_value, sales)
score_inv = score_by_inverse_threshold(inv_to_sales, good=0.15, warn=0.30) if inv_to_sales is not None else None

# 총점(가중치)
scores = {
    "수익성(총이익률)": score_gm,
    "수익성(영업이익률)": score_om,
    "품질(불량률)": score_def,
    "품질(수율)": score_yield,
    "납기(준수율)": score_otd,
    "재고(재고/매출)": score_inv
}

weights = {
    "수익성(총이익률)": 0.22,
    "수익성(영업이익률)": 0.22,
    "품질(불량률)": 0.18,
    "품질(수율)": 0.18,
    "납기(준수율)": 0.12,
    "재고(재고/매출)": 0.08
}

weighted_items = [(k, v, weights[k]) for k, v in scores.items() if v is not None]
total_score = None
if weighted_items:
    total_score = float(sum(v*w for _, v, w in weighted_items) / sum(w for _, _, w in weighted_items))

st.subheader("3) KPI 요약")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("매출", "-" if sales is None else f"{sales:,.0f}")
k2.metric("총이익률", "-" if gross_margin is None else f"{gross_margin*100:.1f}%")
k3.metric("영업이익률(추정)", "-" if op_margin is None else f"{op_margin*100:.1f}%")
k4.metric("불량률", "-" if defect_rate is None else f"{defect_rate*100:.2f}%")
k5.metric("납기준수율", "-" if on_time_rate is None else f"{on_time_rate*100:.1f}%")
k6.metric("종합점수", "-" if total_score is None else f"{total_score:.1f} / 100")

st.divider()

tab1, tab2, tab3 = st.tabs(["📈 재무/수익성", "🏭 생산/품질", "📦 납기/재고"])

with tab1:
    st.subheader("재무/수익성 진단")
    left, right = st.columns([1, 1])
    with left:
        st.write(f"- 총이익률 점수: {traffic_light(score_gm)} {score_gm if score_gm is not None else '-'}")
        st.write(f"- 영업이익률 점수: {traffic_light(score_om)} {score_om if score_om is not None else '-'}")
        st.write("**개선 포인트(룰 기반)**")
        tips = []
        if gross_margin is not None and gross_margin < 0.15:
            tips.append("원가 구조(재료비/외주/불량)와 납품단가 재협상, 제품 믹스 개선이 우선입니다.")
        if op_margin is not None and op_margin < 0.05:
            tips.append("고정비·인건비 구조(간접인력, 잔업, 라인밸런싱)를 점검하고 손익분기점을 낮춰야 합니다.")
        if not tips:
            tips.append("수익성 지표는 양호합니다. 다음 단계로 제품별/고객별 손익분석을 권장합니다.")
        st.write("\n".join([f"• {t}" for t in tips]))
    with right:
        # 단가/원가가 있으면 산포도
        if col_unit_price != "(없음)" and col_unit_cost != "(없음)":
            tmp = df[[col_unit_price, col_unit_cost]].copy()
            tmp.columns = ["단가", "단위원가"]
            tmp["단가"] = to_num(tmp["단가"])
            tmp["단위원가"] = to_num(tmp["단위원가"])
            tmp = tmp.dropna()
            if not tmp.empty:
                fig = px.scatter(tmp, x="단가", y="단위원가", title="단가 vs 단위원가 (마진 구조)")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("단가/단위원가 컬럼을 매핑하면 마진 구조 그래프를 보여줄 수 있습니다.")

with tab2:
    st.subheader("생산/품질 진단")
    left, right = st.columns([1, 1])
    with left:
        st.write(f"- 불량률 점수: {traffic_light(score_def)} {score_def if score_def is not None else '-'}")
        st.write(f"- 수율 점수: {traffic_light(score_yield)} {score_yield if score_yield is not None else '-'}")
        st.write("**개선 포인트(룰 기반)**")
        tips = []
        if defect_rate is not None and defect_rate > 0.03:
            tips.append("불량 TOP 원인(공정/설비/작업자/자재) 파레토 분석 후, 표준작업/검사기준/공정능력 개선이 필요합니다.")
        if yield_rate is not None and yield_rate < 0.95:
            tips.append("수율 저하는 재작업/스크랩 비용을 키웁니다. 공정조건 관리와 초도품 관리 체계를 점검하세요.")
        if not tips:
            tips.append("품질 지표는 양호합니다. 다음 단계로 공정별 불량/라인별 수율로 분해 분석을 권장합니다.")
        st.write("\n".join([f"• {t}" for t in tips]))
    with right:
        if col_prod_qty != "(없음)" and col_defect_qty != "(없음)":
            tmp = df[[col_prod_qty, col_defect_qty]].copy()
            tmp.columns = ["생산수량", "불량수량"]
            tmp["생산수량"] = to_num(tmp["생산수량"])
            tmp["불량수량"] = to_num(tmp["불량수량"])
            tmp = tmp.dropna()
            if not tmp.empty:
                tmp["불량률(행)"] = np.where(tmp["생산수량"] > 0, tmp["불량수량"] / tmp["생산수량"], np.nan)
                tmp = tmp.dropna()
                fig = px.histogram(tmp, x="불량률(행)", nbins=30, title="불량률 분포")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("생산수량/불량수량 컬럼을 매핑하면 불량률 분포를 보여줄 수 있습니다.")

with tab3:
    st.subheader("납기/재고 진단(간이)")
    left, right = st.columns([1, 1])
    with left:
        st.write(f"- 납기준수율 점수: {traffic_light(score_otd)} {score_otd if score_otd is not None else '-'}")
        st.write(f"- 재고/매출 점수: {traffic_light(score_inv)} {score_inv if score_inv is not None else '-'}")
        st.write("**개선 포인트(룰 기반)**")
        tips = []
        if on_time_rate is not None and on_time_rate < 0.90:
            tips.append("납기 지연은 신뢰/패널티로 이어집니다. 병목공정, 외주 리드타임, 자재수급(안전재고)부터 점검하세요.")
        if inv_to_sales is not None and inv_to_sales > 0.30:
            tips.append("재고가 매출 대비 과다합니다. 회전율 관리(ABC, 적정재고)와 생산계획 정확도 개선이 필요합니다.")
        if not tips:
            tips.append("납기/재고 지표는 양호합니다. 다음 단계로 품목별 재고회전/납기지연 원인코드 분석을 권장합니다.")
        st.write("\n".join([f"• {t}" for t in tips]))
    with right:
        if col_due != "(없음)" and col_ship != "(없음)":
            due = pd.to_datetime(df[col_due], errors="coerce")
            ship = pd.to_datetime(df[col_ship], errors="coerce")
            valid = due.notna() & ship.notna()
            if valid.any():
                tmp = pd.DataFrame({
                    "납기일": due[valid],
                    "출고일": ship[valid],
                    "지연일수": (ship[valid] - due[valid]).dt.days
                })
                fig = px.histogram(tmp, x="지연일수", nbins=30, title="납기 지연일수 분포(+)면 지연")
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("납기일/출고일 컬럼을 매핑하면 납기 지연 분포를 보여줄 수 있습니다.")
            
tab4 = st.tabs(["📊 품목/라인 분석"])[0]

with tab4:
    st.subheader("품목/라인/공정별 분해 분석")

    col_item = st.selectbox("품목(선택)", ["(없음)"] + cols)
    col_line = st.selectbox("라인(선택)", ["(없음)"] + cols)
    col_process = st.selectbox("공정(선택)", ["(없음)"] + cols)
    col_defect_reason = st.selectbox("불량사유(선택)", ["(없음)"] + cols)

    if col_item != "(없음)" and col_prod_qty != "(없음)" and col_defect_qty != "(없음)":
        tmp = df[[col_item, col_prod_qty, col_defect_qty]].copy()
        tmp.columns = ["품목", "생산", "불량"]
        tmp["생산"] = pd.to_numeric(tmp["생산"], errors="coerce")
        tmp["불량"] = pd.to_numeric(tmp["불량"], errors="coerce")
        tmp = tmp.groupby("품목").sum().reset_index()
        tmp["불량률"] = tmp["불량"] / tmp["생산"]

        fig = px.bar(tmp.sort_values("불량률", ascending=False),
                     x="품목", y="불량률",
                     title="품목별 불량률")
        st.plotly_chart(fig, use_container_width=True)

    if col_line != "(없음)" and col_good_qty != "(없음)" and col_prod_qty != "(없음)":
        tmp2 = df[[col_line, col_good_qty, col_prod_qty]].copy()
        tmp2.columns = ["라인", "양품", "생산"]
        tmp2["양품"] = pd.to_numeric(tmp2["양품"], errors="coerce")
        tmp2["생산"] = pd.to_numeric(tmp2["생산"], errors="coerce")
        tmp2 = tmp2.groupby("라인").sum().reset_index()
        tmp2["수율"] = tmp2["양품"] / tmp2["생산"]

        fig2 = px.bar(tmp2.sort_values("수율"),
                      x="라인", y="수율",
                      title="라인별 수율 비교")
        st.plotly_chart(fig2, use_container_width=True)

    if col_defect_reason != "(없음)" and col_defect_qty != "(없음)":
        tmp3 = df[[col_defect_reason, col_defect_qty]].copy()
        tmp3.columns = ["불량사유", "불량"]
        tmp3["불량"] = pd.to_numeric(tmp3["불량"], errors="coerce")
        tmp3 = tmp3.groupby("불량사유").sum().reset_index()
        tmp3 = tmp3.sort_values("불량", ascending=False)

        fig3 = px.bar(tmp3,
                      x="불량사유", y="불량",
                      title="불량사유 파레토")
        st.plotly_chart(fig3, use_container_width=True)
        
st.divider()

st.subheader("4) 진단 결과 요약(컨설팅용 복사)")
summary = []
summary.append(f"- 종합점수: {'-' if total_score is None else f'{total_score:.1f}/100'}")
summary.append(f"- 수익성: 총이익률 {'-' if gross_margin is None else f'{gross_margin*100:.1f}%'} / 영업이익률 {'-' if op_margin is None else f'{op_margin*100:.1f}%'}")
summary.append(f"- 품질: 불량률 {'-' if defect_rate is None else f'{defect_rate*100:.2f}%'} / 수율 {'-' if yield_rate is None else f'{yield_rate*100:.2f}%'}")
summary.append(f"- 납기: 준수율 {'-' if on_time_rate is None else f'{on_time_rate*100:.1f}%'}")
if inv_to_sales is not None:
    summary.append(f"- 재고: 재고/매출 {'-' if inv_to_sales is None else f'{inv_to_sales*100:.1f}%'}")

# 리스크 리스트
risk_rows = []
for k, v in scores.items():
    if v is None:
        continue
    if v < 60:
        risk_rows.append(f"  - 🔴 {k}: 기준 미달(점수 {v})")
    elif v < 85:
        risk_rows.append(f"  - 🟠 {k}: 개선 권장(점수 {v})")

summary.append("- 주요 리스크:")
summary.extend(risk_rows if risk_rows else ["  - 🟢 특별한 경고 없음(룰 기반)"])

st.code("\n".join(summary), language="markdown")
