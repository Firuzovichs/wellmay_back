import os
import subprocess

def download_audio(youtube_url, order_id):
    os.makedirs('musics', exist_ok=True)

    try:
        print("Yuklanmoqda...")

        output_file = f"{order_id}.%(ext)s"
        cmd = [
            'yt-dlp',
            '--no-check-certificate',
            '--no-playlist',
            '--extract-audio',
            '--audio-format', 'mp3',
            '--audio-quality', '0',
            '--format', 'bestaudio/best',
            '-o', f'musics/{output_file}',
            youtube_url
        ]

        print("Command:", ' '.join(cmd))  # debug uchun

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            print("Xatolik:", result.stderr)
            return None

        print("✅ Yuklab olindi:", result.stdout)
        return order_id

    except Exception as e:
        print(f"❌ Umumiy xatolik: {e}")
        return None
