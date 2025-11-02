import discord
from discord import app_commands
from discord.ext import commands
import requests
import os 
from datetime import datetime, timezone, timedelta
from flask import Flask
from threading import Thread

# (ส่วนของ Flask สำหรับ Host 24/7)
app = Flask('')
@app.route('/')
def home():
    return "I'm alive!"
def run_flask():
    app.run(host='0.0.0.0', port=8080)
def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ----------------- (1) ตั้งค่า -----------------
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OWM_API_KEY = os.environ.get('OWM_API_KEY')

intents = discord.Intents.default()
# *** (เพิ่มบรรทัดนี้!) ***
intents.members = True # <<< เปิดสิทธิ์ในการเข้าถึงข้อมูลสมาชิก (จำเป็นสำหรับนับคน)

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------- (2) ฟังก์ชันคำแนะนำสุขภาพ (เกณฑ์ประเทศไทย) -----------------
def get_health_advice(temp, feels_like, main_weather_en, humidity):
    advice_list = []
    if main_weather_en == "Thunderstorm":
        advice_list.append("ฝนตกหนัก หากเดินทางด้วยรถจักรยานยนต์ ควรจอดพักรอฝนก่อนดีกว่า ")
    elif main_weather_en == "Rain" or main_weather_en == "Drizzle":
        advice_list.append("ฝนตก อย่าลืมพกร่มและเสื้อกันฝนล่ะ ระวังเป็นไข้นะ! ")
    
    if feels_like >= 40:
        advice_list.append("โห!อากาศร้อนมากเลยนั่นน่ะ อย่าลืมดื่่มน้ำและอย่าพยายามออกไปที่โล่งนะ ")
    elif feels_like >= 35:
        advice_list.append("อากาศร้อนเลยนะ ดื่มน้ำเยอะๆ และอย่าลืมทาครีมกันแดดนะ ")
    
    if temp <= 20:
        advice_list.append("อากาศหนาวมากเลย ใส่เสื้อหนาๆ ทำให้ร่างกายอบอุ่นเข้าไว้นะ ")
    elif temp <= 23:
         advice_list.append("อากาศกำลังเย็นสบายเลย น่านอนนะว่ามั้ย ")

    if humidity > 80 and feels_like >= 32 and not any("ร้อน" in s for s in advice_list):
        advice_list.append("อากาศอบอ้าว อย่าสวมเสื้อหนาเกินไปล่ะ และอยู่ในที่อากาศถ่ายเทด้วยนะ ")

    if main_weather_en == "Clear" and not advice_list:
        advice_list.append("อากาศดี ท้องฟ้าสดใสมาก ออกไปทำกิจกรรมกันเถอะ ")

    if not advice_list:
        return "อากาศปกติครับ รักษาสุขภาพด้วยนะ "
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

# ----------------- (4) ฟังก์ชันตรรกะหลัก (Logic) (เหมือนเดิม) -----------------
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

# ----------------- (5) คำสั่ง Slash Command (ไทย/อังกฤษ) (เหมือนเดิม) -----------------
@bot.tree.command(name="weather", description="Check weather, temperature, and time")
@app_commands.describe(city="The name of the city (e.g., Bangkok)")
async def weather(interaction: discord.Interaction, city: str):
    await _internal_weather_logic(interaction, city)

@bot.tree.command(name="อากาศ", description="เช็คสภาพอากาศ, อุณหภูมิ, และเวลา")
@app_commands.describe(city="ชื่อเมืองที่ต้องการค้นหา (เช่น กรุงเทพ)")
async def akat(interaction: discord.Interaction, city: str):
    await _internal_weather_logic(interaction, city)

# ----------------- (X) *** (เพิ่มฟังก์ชันนี้!) คำสั่งดูสถิติ *** -----------------
@bot.tree.command(name="stats", description="ดูสถิติของบอท (จำนวนเซิร์ฟเวอร์และผู้ใช้)")
async def stats(interaction: discord.Interaction):
    
    # นับจำนวนเซิร์ฟเวอร์ที่บอทอยู่
    server_count = len(bot.guilds)
    
    # นับจำนวนผู้ใช้ทั้งหมด
    # (เราจำเป็นต้องเปิด 'members' intent ที่บรรทัด 30 เพื่อให้ตัวเลขนี้แม่นยำ)
    total_users = sum(guild.member_count for guild in bot.guilds)
    
    embed = discord.Embed(
        title="📊 สถิติของบอท",
        description="นี่คือข้อมูลสถิติการใช้งานบอทของฉันในปัจจุบัน",
        color=discord.Color.green()
    )
    embed.add_field(name="จำนวนเซิร์ฟเวอร์ 🖥️", value=f"{server_count} เซิร์ฟเวอร์", inline=False)
    embed.add_field(name="จำนวนผู้ใช้ทั้งหมด 👥", value=f"{total_users} คน", inline=False)
    
    # ส่งข้อความแบบ "เห็นเฉพาะเรา" (ephemeral=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

    
# ----------------- (6) รันบอท และ ปลุกเว็บ (เหมือนเดิม) -----------------
if BOT_TOKEN is None or OWM_API_KEY is None:
    print("Error: ไม่พบ BOT_TOKEN หรือ OWM_API_KEY")
    print("กรุณาตั้งค่า Environment Variables บน Render.com")
else:
    keep_alive() 
    try:
        bot.run(BOT_TOKEN)
    except discord.errors.LoginFailed:
        print("Error: ใส่ Bot Token ไม่ถูกต้อง หรือ Token ผิด")
    except Exception as e:
        print(f"เกิดข้อผิดพลาดในการรันบอท: {e}")

