import discord
from discord import app_commands
from discord.ext import commands
import requests
import os 
from datetime import datetime, timezone, timedelta
from flask import Flask
from threading import Thread

app = Flask('')
@app.route('/')
def home():
    return "ตื่นแล้วจ้า!"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

BOT_TOKEN = os.environ.get('BOT_TOKEN')
OWM_API_KEY = os.environ.get('OWM_API_KEY')

intents = discord.Intents.default()
intents.members = True 

bot = commands.Bot(command_prefix="!", intents=intents)

# --- ฟังก์ชันให้คำแนะนำ (Logic เดิมที่ปรับปรุง) ---
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

# --- คำสั่งทำนายอากาศ (New Feature) ---
@bot.tree.command(name="predict", description="วิเคราะห์และทำนายสภาพอากาศล่วงหน้า")
@app_commands.describe(city="ชื่อเมืองที่ต้องการให้วิเคราะห์")
async def predict(interaction: discord.Interaction, city: str):
    await interaction.response.defer()
    
    # ใช้ API Forecast 5 days / 3 hours
    forecast_url = f"http://api.openweathermap.org/data/2.5/forecast?appid={OWM_API_KEY}&q={city}&units=metric&lang=th"
    
    try:
        response = requests.get(forecast_url)
        data = response.json()
        
        if data["cod"] == "200":
            # ดึงข้อมูล 3 ช่วงเวลาถัดไป (ประมาณ 9 ชั่วโมงข้างหน้า) มาวิเคราะห์แนวโน้ม
            forecast_list = data["list"][:3] 
            city_name = data["city"]["name"]
            
            # สรุปภาพรวมการทำนาย
            avg_temp = sum(item["main"]["temp"] for item in forecast_list) / len(forecast_list)
            main_condition = forecast_list[1]["weather"][0]["main"] # ดูช่วงกลางของระยะทำนาย
            desc_th = forecast_list[1]["weather"][0]["description"]
            humidity = forecast_list[1]["main"]["humidity"]

            # คำแนะนำจากการวิเคราะห์
            advice = get_health_advice(avg_temp, avg_temp, main_condition, humidity, is_forecast=True)

            embed = discord.Embed(
                title=f"🔮 ผลการวิเคราะห์สภาพอากาศ: {city_name}",
                description=f"วิเคราะห์แนวโน้มในอีก 9-12 ชั่วโมงข้างหน้า",
                color=discord.Color.purple()
            )
            embed.add_field(name="แนวโน้มอากาศ", value=desc_th.capitalize(), inline=True)
            embed.add_field(name="อุณหภูมิเฉลี่ยโดยประมาณ", value=f"{avg_temp:.1f}°C", inline=True)
            embed.add_field(name="📊 การวิเคราะห์และคำแนะนำ", value=advice, inline=False)
            embed.set_footer(text="ข้อมูลวิเคราะห์เชิงสถิติจาก OpenWeatherMap")
            
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send(f"ไม่พบข้อมูลเมือง '{city}' สำหรับการวิเคราะห์")
            
    except Exception as e:
        print(f"Prediction Error: {e}")
        await interaction.followup.send("เกิดข้อผิดพลาดในการวิเคราะห์ข้อมูล")

# ----------------- (คำสั่งเดิมอื่นๆ คงไว้) -----------------

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
            temp = main["temp"]
            health_advice = get_health_advice(temp, main["feels_like"], weather_data["main"], main["humidity"])
            
            embed = discord.Embed(title=f"🏙️ สภาพอากาศ: {data['name']}", color=discord.Color.blue())
            embed.add_field(name="อุณหภูมิ 🌡️", value=f"{temp}°C", inline=True)
            embed.add_field(name="ลักษณะอากาศ", value=weather_data["description"], inline=True)
            embed.add_field(name="💡 คำแนะนำ", value=health_advice, inline=False)
            await interaction.followup.send(embed=embed)
        else:
            await interaction.followup.send("ไม่พบเมืองนี้ครับ")
    except Exception as e:
        await interaction.followup.send("เกิดข้อผิดพลาด")

@bot.tree.command(name="weather", description="Check current weather")
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
    print(f'{bot.user.name} Ready!')

if BOT_TOKEN and OWM_API_KEY:
    keep_alive()
    bot.run(BOT_TOKEN)
