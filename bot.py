import discord
from discord import app_commands
from discord.ext import commands
import requests
import os 
from datetime import datetime, timezone, timedelta
from flask import Flask
from threading import Thread

# ----------------- (1) เว็บเซิร์ฟเวอร์สำหรับ Keep Alive -----------------
app = Flask('')
@app.route('/')
def home():
    return "ตื่นแล้วจ้า!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ----------------- (2) ตั้งค่าบอทและ API -----------------
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OWM_API_KEY = os.environ.get('OWM_API_KEY')

intents = discord.Intents.default()
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------- (3) ฟังก์ชันวิเคราะห์และให้คำแนะนำ -----------------
def get_health_advice(temp, feels_like, main_weather_en, humidity, is_forecast=False):
    advice_list = []
    prefix = "คาดว่า" if is_forecast else ""

    if main_weather_en in ["Thunderstorm", "Rain", "Drizzle"]:
        advice_list.append(f"{prefix}ฝนจะตก เตรียมร่มหรือเสื้อกันฝนไว้ด้วยนะ")
    
    if feels_like >= 35:
        advice_list.append(f"{prefix}อากาศจะร้อนจัด ดื่มน้ำเยอะๆ และระวังฮีทสโตรก")
    elif temp <= 22:
        advice_list.append(f"{prefix}อากาศจะค่อนข้างเย็น รักษาสุขภาพด้วย")

    if humidity > 80 and not any("ฝน" in s for s in advice_list):
        advice_list.append("ความชื้นสูง อากาศอาจจะอบอ้าวเป็นพิเศษ")

    return "\n".join(f"- {advice}" for advice in advice_list) if advice_list else "สภาพอากาศปกติ รักษาสุขภาพด้วยครับ"

# ----------------- (4) คำสั่งทำนายอากาศ (ระบุชั่วโมงได้) -----------------
@bot.tree.command(name="predict", description="วิเคราะห์และทำนายสภาพอากาศล่วงหน้าตามจำนวนชั่วโมง")
@app_commands.describe(city="ชื่อเมือง", hours="จำนวนชั่วโมงที่ต้องการดู (3-120)")
async def predict(interaction: discord.Interaction, city: str, hours: int):
    await interaction.response.defer()
    
    if hours < 1: hours = 3 # ป้องกันใส่เลขน้อยไป
    if hours > 120:
        await interaction.followup.send("ขออภัยครับ ทำนายล่วงหน้าได้สูงสุด 120 ชั่วโมง (5 วัน)")
        return

    forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?appid={OWM_API_KEY}&q={city}&units=metric&lang=th"
    
    try:
        response = requests.get(forecast_url)
        data = response.json()
        
        if data["cod"] == "200":
            forecast_list = data["list"]
            # API ส่งข้อมูลทุก 3 ชม. (index 0=ปัจจุบัน/3ชม., 1=6ชม., ...)
            idx = round(hours / 3) - 1
            if idx < 0: idx = 0
            if idx >= len(forecast_list): idx = len(forecast_list) - 1

            target = forecast_list[idx]
            dt_txt = target["dt_txt"]
            # แปลงรูปแบบเวลาให้ดูง่าย
            dt_obj = datetime.strptime(dt_txt, '%Y-%m-%d %H:%M:%S') + timedelta(hours=7) # ปรับเป็นเวลาไทย
            display_time = dt_obj.strftime("%d/%m/%Y เวลา %H:%M น.")

            temp = target["main"]["temp"]
            condition = target["weather"][0]["main"]
            desc = target["weather"][0]["description"]
            hum = target["main"]["humidity"]

            advice = get_health_advice(temp, temp, condition, hum, is_forecast=True)

            embed = discord.Embed(
                title=f"🔮 ผลการทำนายอากาศ: {data['city']['name']}",
                description=f"วิเคราะห์ล่วงหน้าประมาณ **{hours} ชั่วโมง**",
                color=discord.Color.purple()
            )
            embed.add_field(name="🕒 คาดการณ์ ณ วันที่", value=display_time, inline=False)
            embed.add_field(name="อุณหภูมิ 🌡️", value=f"{temp}°C", inline=True)
            embed.add_field(name="ลักษณะอากาศ", value=desc.capitalize(), inline=True)
            embed.add_field(name="📊 การวิเคราะห์", value=advice, inline=False)
            embed.set_footer(text="ข้อมูลเชิงสถิติจาก OpenWeatherMap")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"ไม่พบข้อมูลเมือง '{city}'")
    except Exception as e:
        print(f"Error: {e}")
        await interaction.followup.send("เกิดข้อผิดพลาดในการวิเคราะห์ข้อมูล")

# ----------------- (5) คำสั่งเดิม (Weather & Stats) -----------------
async def _internal_weather_logic(interaction: discord.Interaction, city: str):
    await interaction.response.defer() 
    base_url = "http://api.openweathermap.org/data/2.5/weather?"
    url = f"{base_url}appid={OWM_API_KEY}&q={city}&units=metric&lang=th" 

    try:
        res = requests.get(url).json()
        if res["cod"] == 200:
            main = res["main"]
            weather = res["weather"][0]
            advice = get_health_advice(main["temp"], main["feels_like"], weather["main"], main["humidity"])
            
            embed = discord.Embed(title=f"🏙️ สภาพอากาศ: {res['name']}", color=discord.Color.blue())
            embed.add_field(name="อุณหภูมิ 🌡️", value=f"{main['temp']}°C", inline=True)
            embed.add_field(name="ลักษณะอากาศ", value=weather["description"], inline=True)
            embed.add_field(name="💡 คำแนะนำ", value=advice, inline=False)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("ไม่พบเมืองนี้ครับ")
    except:
        await interaction.followup.send("เกิดข้อผิดพลาด")

@bot.tree.command(name="weather", description="เช็คสภาพอากาศปัจจุบัน")
async def weather(interaction: discord.Interaction, city: str):
    await _internal_weather_logic(interaction, city)

@bot.tree.command(name="stats", description="ดูสถิติของบอท")
async def stats(interaction: discord.Interaction):
    server_count = len(bot.guilds)
    total_users = sum(guild.member_count for guild in bot.guilds)
    embed = discord.Embed(title="📊 สถิติของบอท", color=discord.Color.green())
    embed.add_field(name="เซิร์ฟเวอร์", value=f"{server_count}", inline=True)
    embed.add_field(name="ผู้ใช้รวม", value=f"{total_users}", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Log in as {bot.user.name}')

# ----------------- (6) รันบอท -----------------
if BOT_TOKEN and OWM_API_KEY:
    keep_alive()
    bot.run(BOT_TOKEN)
