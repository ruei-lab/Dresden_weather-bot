import requests
import time
import schedule
import json
from datetime import datetime
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = 8494809982
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  

last_update_id = 0

# --- 1. 設定與基礎功能 ---

def send_telegram_message(message):
    # 這裡不需要再定義 TOKEN 了，它會直接用上面的 TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    keyboard = {
        "keyboard": [
            ["24-hour forecast", "Current safety alerts"],
            ["Runner’s weather analysis", "Driving condition assessment"]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }
    

    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "reply_markup": json.dumps(keyboard)
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Failed: {e}")

def fetch_weather():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": 51.0504,  # Dresden
        "longitude": 13.7373,
        "hourly": "temperature_2m,windspeed_10m,precipitation",
        "timezone": "Europe/Berlin"
    }
    start_time = time.time()   
    response = requests.get(url, params=params)
    end_time = time.time()     

    latency_ms = (end_time - start_time) * 1000
    print(f"Open-Meteo API Latency: {latency_ms:.2f} ms")
    #response = requests.get(url, params=params)
    return response.json()

#gemini conversation

client = genai.Client(api_key=GEMINI_API_KEY)

def ask_gemini(user_question, weather_data, active_alerts):
   
    # 取得目前時刻的天氣概況
    current_hour = datetime.now().hour
    try:
        if weather_data:
            current_temp = weather_data["hourly"]["temperature_2m"][current_hour]
            current_rain = weather_data["hourly"]["precipitation"][current_hour]
            current_wind = weather_data["hourly"]["windspeed_10m"][current_hour]
            current_summary = f"Current (Now): {current_temp}°C, Rain {current_rain}mm, Wind {current_wind}km/h"
    except:
            current_summary = "Current weather data unavailable."



    forecast_text="\nFORECAST (Next 24 Hours):\n"

    try:

        for i in range(1,9):
            future_idx=current_hour+(i*3)

            # 確保索引不超出範圍 (Open-Meteo 通常給 7 天，所以 24 小時很安全)
            if future_idx < len(weather_data["hourly"]["time"]):
                f_time = weather_data["hourly"]["time"][future_idx][-5:] # 只取 HH:MM
                f_temp = weather_data["hourly"]["temperature_2m"][future_idx]
                f_rain = weather_data["hourly"]["precipitation"][future_idx]
                forecast_text += f"- {f_time}: {f_temp}°C, Rain {f_rain}mm\n"
    except Exception as e:
        forecast_text += f"(Forecast data error: {e})\n"

    #處理警報
    alerts_text=""
    if active_alerts:
        alerts_text="\n SYSTEM DETECTED RISKS (Critical Context Rules):\n"
        for alert in active_alerts:
            alerts_text += f"- Context: {alert['context']} -> Action: {alert['action']}\n"
        alerts_text += "INSTRUCTION: You MUST mention these risks first if they are relevant.\n"

    # 設計 Prompt (提示詞)
    prompt = (
        f"You are a helpful weather assistant. Current weather in Dresden, Germany.\n"
        f"Here is the real-time data:\n"
        f"1. {current_summary}\n"
        f"2. {forecast_text}\n"
        f"{alerts_text}"
        f"Based on the weather data above, please answer the user's question: {user_question}\n"
        f"IMPORTANT: Please reply in ENGLISH. If the user asks about clothing or transport, provide specific safety advice based on the weather conditions."
    )

    try:
        start_llm = time.time()   # ⬅️ 加這行
        response = client.models.generate_content(model="gemini-2.5-flash", 
            contents=prompt)
        return response.text
    except Exception as e:
        return f"Gemini is busy: {e}"

def check_incoming_messages():
    """Receiving Msg from Telegram """
    global last_update_id
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
    params = {"offset": last_update_id + 1, "timeout": 1} 
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if "result" in data:
            for update in data["result"]:
                last_update_id = update["update_id"] 
                
                # 確保是文字訊息
                if "message" in update and "text" in update["message"]:
                    user_text = update["message"]["text"]
                    pipeline_start = time.time()
                    print(f" Reciving the msg: {user_text}")
                    
                    # 1. 抓取最新天氣
                    weather_data = fetch_weather()
                    
                    current_hour = datetime.now().hour
                    t = weather_data["hourly"]["temperature_2m"][current_hour]
                    w = weather_data["hourly"]["windspeed_10m"][current_hour]
                    p = weather_data["hourly"]["precipitation"][current_hour] or 0
                    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                    


                    #detecitaved
                    active_alerts = detect_events(current_time, t, w, p)

                    # 2. 問 Gemini
                    send_telegram_message("Thinking...")
                    ai_reply = ask_gemini(user_text, weather_data, active_alerts)
                    
                    
                    pipeline_end = time.time()
                    total_latency = (pipeline_end - pipeline_start) * 1000
                    print(f"Total Response Time: {total_latency:.2f} ms")                   

                    # 3. 回覆用戶
                    send_telegram_message(f" Gemini:\n{ai_reply}")

    except Exception as e:
        print(f"Error: {e}")


# --- 2. 擴充後的行動資料集 (加入情境 Context) ---

ACTIONS_DATASET =[
    # === Scenario B: Driver / In-Car ===
    {
        "id": 1,
        "category": "Driving Safety",
        "user_context": "Driving",
        "situation": "Black Ice Risk",
        "action": "Possible black ice (Temp <= 3°C)! Avoid sudden braking and maintain double distance.",
        "trigger_condition": lambda t, w, p: t <= 3
    },
    {
        "id": 2,
        "category": "Driving Visibility",
        "user_context": "Driving",
        "situation": "Heavy Rain",
        "action": "Heavy Rain (>2mm). Turn on headlights and watch out for hydroplaning.",
        "trigger_condition": lambda t, w, p: p > 2.0
    },
    {
        "id": 3,
        "category": "Driving Safety",
        "user_context": "Driving",
        "situation": "Snowfall",
        "action": "Heavy Snow! Visibility reduced. Turn on low beams/fog lights and increase distance.",
        # 新增：駕駛的大雪警報 (氣溫低於0且有降水)
        "trigger_condition": lambda t, w, p: t <= 0 and p > 0
    },
    {
        "id": 4,
        "category": "Driving Stability",
        "user_context": "Driving",
        "situation": "Strong Wind",
        "action": "Strong crosswinds (>40km/h). Hold the steering wheel firmly.",
        "trigger_condition": lambda t, w, p: w >38 #(38-49) 
    },

    # === Scenario C: Two-Wheelers (Motorcycle / Bicycle) ===
    {
        "id": 5,
        "category": "Riding Safety",
        "user_context": "Motorcycle / Bicycle",
        "situation": "Strong Crosswind",
        "action": "Caution: Strong crosswinds. Don't go outside.",
        "trigger_condition": lambda t, w, p: 50 < w
    },
    {
        "id": 6,
        "category": "Severe Wind Risk",
        "user_context": "Motorcycle / Bicycle",
        "situation": "Gale Force Winds",
        "action": "DANGER! Winds > 50km/h. Highly recommended to dismount or avoid riding.",
        "trigger_condition": lambda t, w, p: w > 38
    },
    {
        "id": 7,
        "category": "Slippery Road",
        "user_context": "Motorcycle / Bicycle",
        "situation": "Light Rain / Wet Surface",
        "action": "Road surface is wet. Avoid white lane markings and tram tracks.",
        # 修改：設定上限 2.0，因為 > 2.0 會觸發下面的「大雨警報」
        "trigger_condition": lambda t, w, p: 0 < p <= 2.0 and t > 0
    },
    {
        "id": 8,
        "category": "Riding Visibility",
        "user_context": "Motorcycle / Bicycle",
        "situation": "Heavy Rain",
        "action": "Heavy Rain! Visor may fog up and braking distance increases. Ride with extreme caution.",
        # 新增：騎士的大雨警報 (視線與水漂)
        "trigger_condition": lambda t, w, p: p > 2.0 and t > 0
    },
    {
        "id": 9,
        "category": "Winter Riding",
        "user_context": "Motorcycle / Bicycle",
        "situation": "Snow / Icy Roads",
        "action": "Snow detected! Zero traction. Consider walking your bike.",
        "trigger_condition": lambda t, w, p: t <= 0 and p > 0
    },
    {
        "id": 10,
        "category": "Heat Safety",
        "user_context": "Motorcycle / Bicycle",
        "situation": "Extreme Heat",
        "action": "High heat (>30°C)! Asphalt may become soft. Watch out for heat exhaustion.",
        "trigger_condition": lambda t, w, p: t > 30
    },

    # === Scenario D: Outdoor Exercise (Runner/Pedestrian) ===
    {
        "id": 11,
        "category": "Exercise Health",
        "user_context": "Runner/Pedestrian",
        "situation": "Low Temperature",
        "action": "Cold air (<5°C) may irritate lungs. Wear a neck gaiter and extend warm-up.",
        "trigger_condition": lambda t, w, p: t < 5
    },
    {
        "id": 12,
        "category": "Heat Risk",
        "user_context": "Runner/Pedestrian",
        "situation": "High Temperature",
        "action": "High temp (>25°C). Reduce intensity and hydrate every 15 mins. Stay in shade.",
        "trigger_condition": lambda t, w, p: t > 25
    },
    {
        "id": 13,
        "category": "Safety",
        "user_context": "Runner/Pedestrian",
        "situation": "Snow / Icy Ground",
        "action": "Icy ground! Wear boots/shoes with grip or use spikes. Shorten stride.",
        "trigger_condition": lambda t, w, p: t <= 0 and p > 0
    },
    {
        "id": 14,
        "category": "Visibility",
        "user_context": "Runner/Pedestrian",
        "situation": "Light Rain",
        "action": "Light rain. Wear reflective clothing and a cap to keep rain out of eyes.",
        # 修改：設定上限 2.0，區分小雨
        "trigger_condition": lambda t, w, p: 0 < p <= 2.0 and t > 0
    },
    {
        "id": 15,
        "category": "Activity Advice",
        "user_context": "Runner/Pedestrian",
        "situation": "Heavy Rain",
        "action": "Heavy Rain (>2mm)! Consider indoor exercises or treadmill today.",
        # 新增：跑者的大雨警報 (建議改室內)
        "trigger_condition": lambda t, w, p: p > 2.0 and t > 0
    },
    {
        "id": 16,
        "category": "Safety",
        "user_context": "Runner/Pedestrian",
        "situation": "Strong Wind",
        "action": "Strong wind (>30km/h). Watch out for falling branches in parks.",
        "trigger_condition": lambda t, w, p: w > 38
    },

    # === Scenario E: Household Living ===
    {
        "id": 17,
        "category": "Household Advice",
        "user_context": "At Home",
        "situation": "Good for Drying Laundry",
        "action": "Perfect Laundry Weather! No rain + breeze.",
        "trigger_condition": lambda t, w, p: p == 0 and t > 10 and w > 5
    },
    {
        "id": 18,
        "category": "Household Reminder",
        "user_context": "At Home",
        "situation": "Sudden Rain",
        "action": "It's raining! Bring in the laundry!",
        "trigger_condition": lambda t, w, p: p > 0
    },
    {
        "id": 19,
        "category": "Heatwave Alert",
        "user_context": "General Public",
        "situation": "Extreme Heat",
        "action": "Heatwave Alert (>30°C). Stay hydrated and avoid direct sun.",
        "trigger_condition": lambda t, w, p: t > 30
    }
]
    


# --- 3. 核心邏輯 ---
def detect_events(time_str, temp, wind, precip):
    """根據天氣數據偵測觸發事件，並回傳所有符合的情境"""
    triggered_events = []
    
    for item in ACTIONS_DATASET:
        # 檢查是否符合條件
        if item["trigger_condition"](temp, wind, precip):
            triggered_events.append({
                "time": time_str,
                "context": item["user_context"],  # 抓取情境
                "situation": item["situation"],
                "action": item["action"]
            })
    
    return triggered_events

def save_events_to_file(all_events, filename="weather_events.json"):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 事件已保存到 {filename}")

# --- 4. 檢查邏輯與通知 ---


# 6. 定時排程工作 (這段是新的，用來取代 monitor_weather_continuously)

def check_weather_alert_job():
    """排程專用的天氣檢查"""
    print(f"\n[{datetime.now()}] Starting Scheduled Weather Alerts...")
    
    # 1. 抓天氣
    data = fetch_weather()
    if not data: return

    # 2. 簡單取第一個小時做檢查
    hourly = data["hourly"]
    current_hour = datetime.now().hour
    t =  hourly["temperature_2m"][current_hour]
    w =  hourly["windspeed_10m"][current_hour]
    p =  hourly["precipitation"][current_hour]
    
    # 3. 偵測有無事件
    # 這裡時間字串用 datetime.now 取代 "Now" 讓它更準確
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    events = detect_events(current_time, t, w, p)
    
    if events:
        msg = f"Scheduled Weather Alerts (T:{t}°C, Rain:{p}mm)\n"
        for e in events:
            msg += f"【{e['context']}】 {e['action']}\n"
        send_telegram_message(msg)
    else:
        print("Weather conditions are normal. No alerts need to be sent")


# 7. 主程式循環 (程式的入口)

def test_rule_accuracy():
    test_cases = [
        {"t": -1, "w": 10, "p": 0, "expected": "Black Ice Risk"},
        {"t": 5, "w": 20, "p": 3, "expected": "Heavy Rain"},
        {"t": 12, "w": 45, "p": 0, "expected": "Strong Wind"},
        {"t": 25, "w": 5, "p": 0, "expected": None},
    ]

    correct = 0

    for case in test_cases:
        events = detect_events("test", case["t"], case["w"], case["p"])

        triggered_situations = [e["situation"] for e in events]

        if case["expected"] is None and not triggered_situations:
            correct += 1
        elif case["expected"] in triggered_situations:
            correct += 1

    accuracy = correct / len(test_cases)
    print(f"Rule Accuracy: {accuracy * 100:.2f}%")

def test_boundary_conditions():
    print("\n Running Boundary Tests...\n")

    test_cases = [
        {"temp": 3.1, "expected": False},
        {"temp": 3.0, "expected": True},
        {"temp": 2.9, "expected": True},
    ]

    for case in test_cases:
        events = detect_events("test", case["temp"], 10, 0)

        black_ice_triggered = any(
            e["situation"] == "Black Ice Risk" for e in events
        )

        print(f"Temp: {case['temp']}°C → Triggered: {black_ice_triggered}")


if __name__ == "__main__":
    print("The System activating...")
    
    test_rule_accuracy()
    test_boundary_conditions()
    
    send_telegram_message("The System activating")

    # 設定排程：每 60 分鐘檢查一次天氣警報
    schedule.every(180).minutes.do(check_weather_alert_job)

    # 立即執行一次天氣檢查 (讓你知道程式有在跑)
    check_weather_alert_job()

    # 無限迴圈：同時處理「對話」與「排程」
    print("Start listening for messages and scheduling tasks...")
    while True:
        try:
            # 1. 檢查排程 (是否有天氣警報要發)
            schedule.run_pending()
            
            # 2. 檢查有沒有人傳訊息來 (聊天功能)
            # 務必確認你的程式碼上面有定義 check_incoming_messages()
            check_incoming_messages()
            
            # 休息一下避免 CPU 飆高
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("The system stop")
            break
        except Exception as e:
            print(f"Forbidden the system reset {e}")
            time.sleep(5)
