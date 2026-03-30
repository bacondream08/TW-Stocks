import streamlit as st
import pandas as pd
from FinMind.data import DataLoader
import datetime
import time
import plotly.express as px

# --- 1. 定義與初始設定 ---
# 您的專屬 API Token
MY_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJkYXRlIjoiMjAyNi0wMy0yNiAxOTowNTowMyIsInVzZXJfaWQiOiJiYWNvbmRyZWFtIiwiZW1haWwiOiJiYWNvbmRyZWFtMDhAZ21haWwuY29tIiwiaXAiOiIxMTQuNDcuNzcuMTY0In0.URFp0XQ2HdtmZXsVObjK3m1NXw3s44ZVRrI8_hPa1Qs"

api = DataLoader()
api.login_by_token(api_token=MY_TOKEN)

st.set_page_config(page_title="台股大戶籌碼監控", layout="wide")

# --- 2. 側邊欄介面 ---
with st.sidebar:
    st.header("📊 篩選參數")
    # 市場分類對應
    market_display = st.multiselect(
        "選擇市場範圍", 
        ["上市", "上櫃", "興櫃"], 
        default=["上市", "上櫃", "興櫃"]
    )
    
    # 轉換成 FinMind API 辨識碼
    market_map = {"上市": "TSE", "上櫃": "OTC", "興櫃": "興櫃"}
    selected_markets = [market_map[m] for m in market_display]
    
    # 掃描數量限制
    scan_count = st.number_input("掃描股票數量 (建議先設100測試)", min_value=10, max_value=2000, value=100)
    
    st.divider()
    st.write("🔍 **篩選邏輯：**")
    st.write("1. 鎖定「1000張以上」大戶級距")
    st.write("2. 檢查最近 4 週數據")
    st.write("3. 滿足：本週 > 前1週 > 前2週 > 前3週")

# --- 3. 核心邏輯函數 ---
def check_continuous_growth(stock_id):
    try:
        # 1. 抓取過去 50 天數據
        df = api.taiwan_stock_holding_shares_per(
            stock_id=stock_id,
            start_date=(datetime.date.today() - datetime.timedelta(days=50)).strftime('%Y-%m-%d')
        )
        
        if df.empty:
            return None

        # 2. 依照日期分組，並抓取每個日期「最後一個級距」(即最大級距)
        # 不管它叫什麼名字，最後一級通常就是大戶
        latest_data = df.groupby('date').tail(1).sort_values('date', ascending=False)
        
        if len(latest_data) >= 4:
            p = latest_data['percent'].tolist()[:4]
            # 注意：下面這一行開頭的空格數量，必須跟上面的 p = ... 一模一樣
            if p[0] > p[3]: 
                return [round(x, 2) for x in p]


        return None
    except Exception:
        return None

# --- 4. 主畫面執行 ---
st.title("📈 台股 1000張大戶「連三增」監控站")

if st.button("🚀 開始掃描全市場"):
    with st.spinner("正在連線雲端資料庫並進行大數據比對..."):
        # 獲取清單
        stock_info = api.taiwan_stock_info()
        filtered_list = stock_info[stock_info['type'].isin(selected_markets)].head(scan_count)
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (idx, row) in enumerate(filtered_list.iterrows()):
            sid, sname, stype = row['stock_id'], row['stock_name'], row['type']
            
            # 更新進度條
            progress_bar.progress((i + 1) / len(filtered_list))
            status_text.text(f"檢查中: {sid} {sname} ({stype})")
            
            data = check_continuous_growth(sid)
            if data:
                results.append({
                    "代碼": sid, "名稱": sname, "市場": stype,
                    "本週(%)": data[0], "前1週(%)": data[1], 
                    "前2週(%)": data[2], "前3週(%)": data[3],
                    "三週累計增幅": round(data[0] - data[3], 2)
                })
            time.sleep(0.05) # 稍微緩衝

        status_text.empty()
        
        if results:
            st.success(f"✅ 掃描完成！共有 {len(results)} 檔符合條件")
            res_df = pd.DataFrame(results)
            
            # 顯示排行圖表
            st.subheader("📊 籌碼增幅排行榜")
            fig = px.bar(res_df, x="名稱", y="三週累計增幅", color="三週累計增幅", text="三週累計增幅")
            st.plotly_chart(fig, use_container_width=True)
            
            # 顯示詳細表格
            st.subheader("📋 詳細數據表")
            st.dataframe(res_df.style.background_gradient(cmap='Reds', subset=['三週累計增幅']), use_container_width=True)
            
            # 匯出 CSV
            csv = res_df.to_csv(index=False).encode('utf-8-sig')
            st.download_button("📥 下載篩選報告 (CSV)", data=csv, file_name=f"big_holder_{datetime.date.today()}.csv")
        else:
            st.warning("目前掃描範圍內無符合條件標的，請嘗試擴大掃描數量。")
