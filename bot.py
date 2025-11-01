import discord
from discord import app_commands
from discord.ext import commands
import requests
import os # 1. Import os
from datetime import datetime, timezone, timedelta

# 2. Import Flask และ Threading (สำหรับ Host 24/7)
from flask import Flask
from threading import Thread

# 3. สร้างแอป Flask
app = Flask('')

# 4. สร้างหน้าเว็บหลัก (สำหรับ UptimeRobot)
@app.route('/')
def home():
    return "I'm alive!"

# 5. ฟังก์ชันรัน Flask
def run_flask():
    app.run(host='0.0.0.0', port=8080)

# 6. ฟังก์ชันเริ่ม Thread (ปลุก Flask)
def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ----------------- (1) ตั้งค่า -----------------
# (!!! เราจะใช้ os.environ.get เพื่อ "อ่าน" Token จาก Render)
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OWM_API_KEY = os.environ.get('OWM_API_KEY')

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------- (2) ฟังก์ชันคำแนะนำสุขภาพ -----------------
def get_health_advice(temp, feels_like, main_weather_en, humidity):
    advice_list = []
    if main_weather_en == "Thunderstorm":
        advice_list.append("พายุฝนฟ้าคะนอง! 🌩️ ควรหลบอยู่ในอาคารที่ปลอดภัย")
    elif main_weather_en == "Rain" or main_weather_en == "Drizzle":
        advice_list.append("ฝนตก ☔ พกร่มหรือเสื้อกันฝน ระวังถนนลื่น")
    
    if feels_like >= 35:
        advice_list.append("อากาศร้อนจัด! 🔥 ดื่มน้ำบ่อยๆ หลีกเลี่ยงการอยู่กลางแดดนานๆ")
    elif feels_like >= 30:
        advice_list.append("อากาศค่อนข้างร้อน ☀️ อย่าลืมดื่มน้ำและทาครีมกันแดด")
    elif temp <= 15:
        advice_list.append("อากาศหนาวเย็น 🥶 สวมเสื้อผ้าให้อบอุ่น")

    if humidity > 85 and feels_like >= 30:
        advice_list.append("ความชื้นสูงและร้อนอบอ้าว ระวัง 'Heat Stroke'")

    if main_weather_en == "Clear" and not advice_list:
        advice_list.append("ท้องฟ้าแจ่มใส ☀️ เหมาะกับการทำกิจกรรม")

    if not advice_list:
        return "อากาศดีปานกลาง รักษาสุขภาพครับ 👍"
    else:
        return "\n".join(f"- {advice}" for advice in advice_list)

# ----------------- (3) อีเวนต์เมื่อบอทพร้อมทำงาน -----------------
@bot.event
async def on_ready():
    print(f"กำลังล็อกอินในชื่อ {bot.user.name}...")
    try:
        synced = await bot.tree.sync()
        print(f"ซิงค์คำสั่ง Slash Command แล้ว {len(synced)} คำสั่ง")
    except Exception as e:
        print(f"ไม่สามารถซิงค์คำสั่งได้: {e}")
        
    print(f'{bot.user.name} ได้ออนไลน์และพร้อมใช้งาน!')
    print('------')

# ----------------- (4) ฟังก์ชันตรรกะหลัก (Logic) -----------------
async def _internal_weather_logic(interaction: discord.Interaction, city: str):
    await interaction.response.defer() 
    base_url = "http://api.openweathermap.org/data/2.5/weather?"
    complete_url = f"{base_url}appid={OWM_API_KEY}&q={city}&units=metric&lang=th" 

    try:
        response = requests.get(complete_url)
        data = response.json()
        if data["cod"] == 200:
            main = data["main"]
            weather_data = data["weather"][0]
            city_name = data["name"]
            country = data["sys"]["country"]
            temp = main["temp"]
            temp_feels_like = main["feels_like"]
            humidity = main["humidity"]
            main_weather_en = weather_data["main"]
            weather_desc_th = weather_data["description"]
            timezone_offset = data["timezone"]
            utc_now = datetime.now(timezone.utc)
            city_offset = timedelta(seconds=timezone_offset)
            city_time = utc_now + city_offset
            time_str = city_time.strftime("%H:%M น.")
            date_str = city_time.strftime("%A, %d %B %Y")
            health_advice = get_health_advice(temp, temp_feels_like, main_weather_en, humidity)
            embed = discord.Embed(title=f"🏙️ สภาพอากาศ: {city_name}, {country}", description=f"ข้อมูล ณ {date_str}", color=discord.Color.blue())
            embed.add_field(name="เวลาท้องถิ่น 🕑", value=time_str, inline=False)
            embed.add_field(name="ลักษณะอากาศ 🌤️", value=weather_desc_th.capitalize(), inline=False)
            embed.add_field(name="อุณหภูมิ 🌡️", value=f"{temp}°C", inline=True)
            embed.add_field(name="รู้สึกเหมือน 🌡️", value=f"{temp_feels_like}°C", inline=True)
            embed.add_field(name="ความชื้น 💧", value=f"{humidity}%", inline=True)
            embed.add_field(name="💡 คำแนะนำสุขภาพ", value=health_advice, inline=False)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"ไม่พบข้อมูลของเมือง '{city}' กรุณาลองใหม่")
    except Exception as e:
        print(f"เกิดข้อผิดพลาด: {e}")
        await interaction.followup.send("เกิดข้อผิดพลาดในการดึงข้อมูลครับ")

# ----------------- (5) คำสั่ง Slash Command (ไทย/อังกฤษ) -----------------
@bot.tree.command(name="weather", description="Check weather, temperature, and time")
@app_commands.describe(city="The name of the city (e.g., Bangkok)")
async def weather(interaction: discord.Interaction, city: str):
    await _internal_weather_logic(interaction, city)

@bot.tree.command(name="อากาศ", description="เช็คสภาพอากาศ, อุณหภูมิ, และเวลา")
@app_commands.describe(city="ชื่อเมืองที่ต้องการค้นหา (เช่น กรุงเทพ)")
async def akat(interaction: discord.Interaction, city: str):
    await _internal_weather_logic(interaction, city)
    
# ----------------- (6) รันบอท และ ปลุกเว็บ -----------------

# (6.1) ตรวจสอบก่อนว่า Token มีค่าหรือไม่
if BOT_TOKEN is None or OWM_API_KEY is None:
    print("Error: ไม่พบ BOT_TOKEN หรือ OWM_API_KEY")
    print("กรุณาตั้งค่า Environment Variables บน Render.com")
else:
    # (6.2) สั่งให้เว็บ Flask (ตัวปลุก) เริ่มทำงาน
    keep_alive() 
    
    # (6.3) รันบอท Discord (ตัวหลัก)
    try:
        bot.run(BOT_TOKEN)
    except discord.errors.LoginFailed:
        print("Error: ใส่ Bot Token ไม่ถูกต้อง หรือ Token ผิด")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการรันบอท: {e}")