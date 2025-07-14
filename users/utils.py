import os
import subprocess

def download_audio(youtube_url, order_id):
    os.makedirs('musics', exist_ok=True)

    try:
        print("Yuklanmoqda...")

        output_file = f"{order_id}.%(ext)s"

        # `yt-dlp` ni tizimdan avtomatik chaqiradi
        subprocess.run([
            'yt-dlp',
            '--no-check-certificate',
            '-f', 'bestaudio',
            '-o', f"musics/{output_file}",
            youtube_url
        ], check=True)

        print(f"Yuklab olindi: Order ID - {order_id}")
        return order_id

    except Exception as e:
        print(f"Xatolik yuz berdi: {e}")
        return None
