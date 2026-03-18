import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import io
import requests
import warnings

# 설정 및 보안 무시
warnings.filterwarnings('ignore')
st.set_page_config(page_title="S&P 500 AI Scanner", layout="wide")

# --- [UI 구성] ---
st.title("🤖 기관 트레이딩 알고리즘 기반 S&P 500 스크리너")
st.sidebar.header("🔍 설정")
score_threshold = st.sidebar.slider("최소 만족 조건 수 (Score)", 1, 4, 2)

if st.button('🚀 실시간 시장 분석 및 스캐닝 시작'):
    
    # --- [STEP 1] 시장 환경 분석 ---
    with st.spinner('전체 시장 환경 분석 중...'):
        idx_df = yf.download("^GSPC", period="1y", progress=False)
        if isinstance(idx_df.columns, pd.MultiIndex):
            idx_df.columns = [col[0] for col in idx_df.columns]
        
        idx_df['SMA20'] = ta.sma(idx_df['Close'], length=20)
        idx_df['SMA50'] = ta.sma(idx_df['Close'], length=50)
        
        curr_idx_close = float(idx_df['Close'].iloc[-1])
        trend_status = "상승장" if curr_idx_close > float(idx_df['SMA20'].iloc[-1]) else "하락/혼조장"
        
        # Fear & Greed Index (우회 로직 생략, 간단히 출력)
        st.subheader("🌎 시장 환경 대시보드")
        col1, col2, col3 = st.columns(3)
        col1.metric("S&P 500 지수", f"{curr_idx_close:,.2f}", f"{trend_status}")
        
    # --- [STEP 2] 스크리닝 로직 ---
    with st.spinner('S&P 500 전 종목 데이터 수집 및 분석 중 (약 1~2분 소요)...'):
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        tables = pd.read_html(io.StringIO(requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text))
        sp500_tickers = [str(t).replace('.', '-') for t in tables[0]['Symbol'].tolist()]
        
        # 속도를 위해 일부만 테스트하거나 전체 실행
        data = yf.download(sp500_tickers, period="1y", interval="1d", progress=False, group_by="ticker")
        results = []

        for ticker in sp500_tickers:
            try:
                df = data[ticker].dropna()
                if len(df) < 200: continue

                # 지표 계산
                df['SMA200'] = ta.sma(df['Close'], length=200)
                df['RSI'] = ta.rsi(df['Close'], length=14)
                df['Vol_SMA20'] = ta.sma(df['Volume'], length=20)
                qqe = ta.qqe(df['Close'])
                
                # 조건 판별 (기존 로직 동일)
                cond_sma = df['Close'].iloc[-1] > df['SMA200'].iloc[-1]
                cond_vol = df['Volume'].iloc[-1] >= (df['Vol_SMA20'].iloc[-1] * 1.5)
                cond_qqe = qqe.iloc[-1, 0] > qqe.iloc[-1, 1] # QQE Fast > Slow
                
                # RSI 다이버전스 (간략화)
                cond_div = df['Close'].iloc[-1] < df['Close'].iloc[-10] and df['RSI'].iloc[-1] > df['RSI'].iloc[-10]

                score = int(cond_sma) + int(cond_vol) + int(cond_qqe) + int(cond_div)

                if score >= score_threshold:
                    results.append({
                        'Ticker': ticker,
                        'Score': f"{score}/4",
                        'Price': f"${round(df['Close'].iloc[-1], 2)}",
                        'SMA200': '⭕' if cond_sma else '❌',
                        'QQE': '⭕' if cond_qqe else '❌',
                        'Volume': '⭕' if cond_vol else '❌',
                        'RSI_Div': '⭕' if cond_div else '❌'
                    })
            except: continue

        # 결과 출력
        if results:
            st.subheader(f"🎉 스크리닝 결과 (조건 {score_threshold}개 이상 만족)")
            res_df = pd.DataFrame(results).sort_values(by='Score', ascending=False)
            st.dataframe(res_df, use_container_width=True)
        else:
            st.warning("조건을 만족하는 종목이 없습니다.")