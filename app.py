import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import requests
import io
import warnings
from datetime import datetime, timedelta

# 경고 메시지 무시 및 페이지 설정
warnings.filterwarnings('ignore')
st.set_page_config(page_title="S&P 500 AI Scanner", layout="wide")

# --- [메인 화면 구성] ---
st.title("🤖 기관 트레이딩 알고리즘 기반 S&P 500 스크리너")
st.markdown("---")

# 사이드바 설정
st.sidebar.header("🔍 필터 설정")
score_threshold = st.sidebar.slider("최소 만족 조건 수 (Score)", 1, 4, 2)
st.sidebar.write("허들이 낮을수록 많은 종목이 검색됩니다.")

# 분석 시작 버튼
if st.button('🚀 실시간 시장 분석 및 스캐닝 시작'):
    
    # --- [STEP 1] 시장 환경 분석 ---
    with st.spinner('전체 시장 환경 분석 중...'):
        try:
            idx_df = yf.download("^GSPC", period="1y", progress=False)
            if isinstance(idx_df.columns, pd.MultiIndex):
                idx_df.columns = [col[0] for col in idx_df.columns]
            
            idx_df['SMA20'] = ta.sma(idx_df['Close'], length=20)
            idx_df['SMA50'] = ta.sma(idx_df['Close'], length=50)
            
            curr_idx_close = float(idx_df['Close'].iloc[-1])
            curr_sma20 = float(idx_df['SMA20'].iloc[-1])
            
            trend_status = "🟢 상승장 (지수가 20일선 위)" if curr_idx_close > curr_sma20 else "🔴 하락/혼조장"
            
            st.subheader("🌎 시장 환경 대시보드")
            col1, col2 = st.columns(2)
            col1.metric("S&P 500 현재가", f"{curr_idx_close:,.2f}")
            col2.metric("현재 시장 추세", trend_status)
        except Exception as e:
            st.error(f"시장 데이터 로드 실패: {e}")

    # --- [STEP 2] 스크리닝 로직 ---
    st.markdown("---")
    with st.spinner('S&P 500 전 종목 분석 중 (약 1~2분 소요)...'):
        try:
            # 위키피디아에서 S&P 500 목록 가져오기
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers)
            tables = pd.read_html(io.StringIO(response.text))
            sp500_tickers = [str(t).replace('.', '-') for t in tables[0]['Symbol'].tolist()]
            
            # 데이터 일괄 다운로드
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
                    
                    # QQE 계산
                    qqe = ta.qqe(df['Close'])
                    
                    # [조건 1] SMA 200 돌파
                    cond_sma = df['Close'].iloc[-1] > df['SMA200'].iloc[-1]
                    # [조건 2] 수급 (거래량 1.5배)
                    cond_vol = df['Volume'].iloc[-1] >= (df['Vol_SMA20'].iloc[-1] * 1.5)
                    # [조건 3] QQE 골든크로스
                    cond_qqe = qqe.iloc[-1, 0] > qqe.iloc[-1, 1]
                    # [조건 4] RSI 다이버전스 (간략)
                    cond_div = df['Close'].iloc[-1] < df['Close'].iloc[-10] and df['RSI'].iloc[-1] > df['RSI'].iloc[-10]

                    score = int(cond_sma) + int(cond_vol) + int(cond_qqe) + int(cond_div)

                    if score >= score_threshold:
                        results.append({
                            'Ticker': ticker,
                            '만족도': f"{score}/4",
                            '현재가': f"${round(df['Close'].iloc[-1], 2)}",
                            'SMA200': '⭕' if cond_sma else '❌',
                            'QQE상승': '⭕' if cond_qqe else '❌',
                            '수급폭발': '⭕' if cond_vol else '❌',
                            '반전신호': '⭕' if cond_div else '❌'
                        })
                except:
                    continue

            # 최종 결과 출력
            if results:
                st.success(f"총 {len(results)}개의 종목이 검색되었습니다.")
                res_df = pd.DataFrame(results).sort_values(by='만족도', ascending=False)
                st.table(res_df) # 웹에서 보기 편하게 표로 출력
            else:
                st.warning("조건을 만족하는 종목이 현재 없습니다.")
                
        except Exception as e:
            st.error(f"스크리닝 도중 오류 발생: {e}")

st.sidebar.markdown("---")
st.sidebar.info("이 도구는 기술적 분석 지표를 기반으로 하며, 모든 투자의 책임은 본인에게 있습니다.")
