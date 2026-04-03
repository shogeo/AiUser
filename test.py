import os
import time
import google.genai as genai

# IPv4 only - критично для VPN
os.environ['CURL_DISABLE_IPV6'] = '1'
os.environ['GENAI_USE_CURL_CFFI'] = '1'
os.environ['HTTPX_FORCE_IPV4'] = '1'

client = genai.Client(api_key="AIzaSyBTAdhoMr4zkbV7V8yc30kZWxOL4TyJ8bw")
file_path = "sticker.webp"

print("Загружаем...")
uploaded_file = client.files.upload(file=file_path)
print("Загружен:", uploaded_file.name)

file_name = uploaded_file.name
while True:
    file_info = client.files.get(name=file_name)
    print("Состояние:", file_info.state.name)
    if file_info.state.name == "ACTIVE":
        model = client.get_model("gemini-3.1-flash-lite-preview")
        response = model.generate_content("Опиши изображение", uploaded_file)
        print("Ответ:", response.text)
        break
    time.sleep(1)