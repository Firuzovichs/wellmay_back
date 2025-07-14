# Python ning yengil versiyasidan boshlaymiz
FROM python:3.11-slim

# Ishchi katalog
WORKDIR /app

# Paketlar ro'yxatini konteynerga nusxalash
COPY requirements.txt .

# Paketlarni o'rnatish

RUN apt-get update && apt-get install -y ffmpeg \
    && pip install --no-cache-dir -r requirements.txt

RUN apt update && apt install -y yt-dlp

# Loyiha fayllarini konteynerga nusxalash
COPY . .

# Django serverni 0.0.0.0 manzilida ishga tushirish
CMD ["gunicorn", "website_back.wsgi:application", "--bind", "0.0.0.0:8001"]
