import discord
from discord import app_commands
from discord.ext import commands
import requests
import os 
from datetime import datetime, timezone, timedelta
from flask import Flask
from threading import Thread

# ----------------- (1) Keep Alive Setup -----------------
app = Flask('')
@app.route('/')
def home():
    return "ตื่นแล้วค้าบบ ไม่ต้องกดแล้วจ้า"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ----------------- (2) Bot Configuration -----------------
BOT_TOKEN = os.environ.get('BOT_TOKEN')
OWM_API_KEY = os.environ.get('OWM_API_KEY')

intents = discord.Intents.default()
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# ----------------- (3) ระบบวิเคราะห์และคำแนะนำสุขภาพ (แบบละเอียด) -----------------
def get_health_advice(temp, feels_like, main_weather_en, humidity, is_forecast=False):
    advice_list = []
    prefix = "คาดว่า" if is_forecast else ""

    # วิเคราะห์เรื่องฝนและพายุ
    if main_weather_en == "Thunderstorm":
        advice_list.append(f"{prefix}พายุฝนฟ้าคะนอง หากเดินทางด้วยรถจักรยานยนต์ ควรจอดพักรอฝนก่อนนะ")
    elif main_weather_en in ["Rain", "Drizzle"]:
        advice_list.append(f"{prefix}ฝนตก อย่าลืมพกร่มและเสื้อกันฝนล่ะ ระวังเป็นไข้นะ!")
    
    # วิเคราะห์ความร้อน
    if feels_like >= 40:
        advice_list.append(f"{prefix}อากาศร้อนจัด! อย่าลืมดื่มน้ำบ่อยๆ และเลี่ยงการออกแดดนานๆ")
    elif feels_like >= 35:
        advice_list.append(f"{prefix}อากาศค่อนข้างร้อน ดื่มน้ำเยอะๆ และทาครีมกันแดดด้วยนะ")
    
    # วิเคราะห์ความหนาว
    if temp <= 20:
        advice_list.append(f"{prefix}อากาศหนาวมาก ใส่เสื้อหนาๆ ทำให้ร่างกายอบอุ่นเสมอนะ")
    elif temp <= 23:
         advice_list.append(f"{prefix}อากาศเย็นสบาย กำลังดีเลย")

    # วิเคราะห์ความชื้นและอากาศอบอ้าว
    if humidity > 80 and feels_like >= 32 and not any("ร้อน" in s for s in advice_list):
        advice_list.append(f"{prefix}อากาศอบอ้าว ควรอยู่ในที่ถ่ายเทและสวมเสื้อผ้าที่ระบายอากาศได้ดี")

    # กรณีท้องฟ้าแจ่มใส
    if main_weather_en == "Clear" and not advice_list:
        advice_list.append(f"{prefix}ท้องฟ้าสดใส ออกไปทำกิจกรรมข้างนอกให้สนุกได้เลย!")

    if not advice_list:
        return "อากาศปกติครับ รักษาสุขภาพด้วยนะ"
    else:
        return "\n".join(f"- {advice}" for advice in advice_list)

# ----------------- (4) คำสั่งทำนายอากาศ (Predict) -----------------
@bot.tree.command(name="predict", description="ทำนายสภาพอากาศล่วงหน้าตามจำนวนชั่วโมงที่กำหนด")
@app_commands.describe(city="ชื่อเมือง", hours="กี่ชั่วโมงข้างหน้า (เช่น 3, 24, 48)")
async def predict(interaction: discord.Interaction, city: str, hours: int):
    await interaction.response.defer()
    
    if hours < 1: hours = 3
    if hours > 120:
        await interaction.followup.send("ทำนายล่วงหน้าได้ไม่เกิน 120 ชั่วโมง (5 วัน) ครับ")
        return

    url = f"http://api.openweathermap.org/data/2.5/forecast?appid={OWM_API_KEY}&q={city}&units=metric&lang=th"
    
    try:
        data = requests.get(url).json()
        if data["cod"] == "200":
            # API ให้ข้อมูลทุก 3 ชม. ดังนั้นต้องหาตำแหน่ง (Index) ที่ใกล้เคียงที่สุด
            idx = round(hours / 3) - 1
            idx = max(0, min(idx, len(data["list"]) - 1))

            target = data["list"][idx]
            # ปรับเวลาแสดงผล (เพิ่ม 7 ชม. สำหรับเวลาไทย)
            dt_obj = datetime.strptime(target["dt_txt"], '%Y-%m-%d %H:%M:%S') + timedelta(hours=7)
            
            temp = target["main"]["temp"]
            feels_like = target["main"]["feels_like"]
            weather_main = target["weather"][0]["main"]
            desc = target["weather"][0]["description"]
            humidity = target["main"]["humidity"]

            # เรียกคำแนะนำสุขภาพ (is_forecast=True)
            advice = get_health_advice(temp, feels_like, weather_main, humidity, is_forecast=True)

            embed = discord.Embed(
                title=f"🔮 พยากรณ์อากาศ: {data['city']['name']}",
                description=f"วิเคราะห์ล่วงหน้าประมาณ **{hours} ชั่วโมง**",
                color=discord.Color.dark_purple()
            )
            embed.add_field(name="🕒 คาดการณ์ ณ เวลา", value=dt_obj.strftime("%d/%m/%Y %H:%M น."), inline=False)
            embed.add_field(name="อุณหภูมิ 🌡️", value=f"{temp}°C (รู้สึกเหมือน {feels_like}°C)", inline=True)
            embed.add_field(name="ความชื้น 💧", value=f"{humidity}%", inline=True)
            embed.add_field(name="ลักษณะอากาศ", value=desc.capitalize(), inline=False)
            embed.add_field(name="📝 วิเคราะห์และคำแนะนำสุขภาพ", value=advice, inline=False)
            embed.set_footer(text="วิเคราะห์ข้อมูลโดยระบบ AI พยากรณ์")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"ไม่พบเมือง '{city}'")
    except:
        await interaction.followup.send("เกิดข้อผิดพลาดในการดึงข้อมูล")

# ----------------- (5) คำสั่งเช็คอากาศปัจจุบัน (Weather) -----------------
@bot.tree.command(name="weather", description="เช็คสภาพอากาศปัจจุบัน")
async def weather(interaction: discord.Interaction, city: str):
    await interaction.response.defer()
    url = f"http://api.openweathermap.org/data/2.5/weather?appid={OWM_API_KEY}&q={city}&units=metric&lang=th"
    
    try:
        res = requests.get(url).json()
        if res["cod"] == 200:
            main = res["main"]
            weather_data = res["weather"][0]
            
            advice = get_health_advice(main["temp"], main["feels_like"], weather_data["main"], main["humidity"])
            
            embed = discord.Embed(title=f"🏙️ อากาศปัจจุบัน: {res['name']}", color=discord.Color.blue())
            embed.add_field(name="อุณหภูมิ 🌡️", value=f"{main['temp']}°C", inline=True)
            embed.add_field(name="ความชื้น 💧", value=f"{main['humidity']}%", inline=True)
            embed.add_field(name="ลักษณะอากาศ", value=weather_data["description"], inline=False)
            embed.add_field(name="💡 คำแนะนำสุขภาพ", value=advice, inline=False)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("ไม่พบเมืองนี้ครับ")
    except:
        await interaction.followup.send("เกิดข้อผิดพลาด")

# ----------------- (6) คำสั่งดูสถิติ (Stats) -----------------
@bot.tree.command(name="stats", description="ดูสถิติของบอท")
async def stats(interaction: discord.Interaction):
    server_count = len(bot.guilds)
    total_users = sum(guild.member_count for guild in bot.guilds)
    embed = discord.Embed(title="📊 สถิติการใช้งาน", color=discord.Color.green())
    embed.add_field(name="จำนวนเซิร์ฟเวอร์", value=f"{server_count}", inline=True)
    embed.add_field(name="จำนวนผู้ใช้รวม", value=f"{total_users}", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Logged in as {bot.user.name} (ID: {bot.user.id})')

# ----------------- (7) Run Bot -----------------
if BOT_TOKEN and OWM_API_KEY:
    keep_alive()
    bot.run(BOT_TOKEN)
