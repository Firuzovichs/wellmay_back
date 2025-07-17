from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import CustomUser,UserProfile,Orders
from rest_framework_simplejwt.tokens import RefreshToken
from django.shortcuts import get_object_or_404
from .serializers import UserCreateSerializer
from .utils import download_audio
from rest_framework.permissions import IsAuthenticated,AllowAny
from openai import OpenAI
import requests
from PIL import Image
from io import BytesIO
import os
import openai
import time
from urllib.parse import urlparse
from django.http import JsonResponse
from pydub import AudioSegment
import ffmpeg
from rest_framework.authentication import TokenAuthentication
import whisper
import logging

logger = logging.getLogger(__name__)

model = whisper.load_model("tiny",device="cpu")

class LastFourOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        print(user)
        orders = Orders.objects.filter(user=user).order_by('-created_at')[:4]
        order_ids = [str(order.order_id) for order in orders]
        return Response({"last_4_order_ids": order_ids})



class VideosToReels(APIView):
    def post(self, request, *args, **kwargs):
        order_id = request.data.get("order_id")
        if not order_id:
            return JsonResponse({"error": "order_id talab qilinadi"}, status=400)
        
        video_dir = f"/var/www/wellmay/videos/{order_id}"
        audio_dir = f"/var/www/wellmay/audio/{order_id}"
        output_dir = f"/var/www/wellmay/reels/{order_id}"
        
        if not os.path.exists(video_dir):
            return JsonResponse({"error": "Video katalogi topilmadi"}, status=404)
        
        if not os.path.exists(audio_dir):
            return JsonResponse({"error": "Audio katalogi topilmadi"}, status=404)
        
        video_files = sorted([os.path.join(video_dir, f) for f in os.listdir(video_dir) if f.endswith(".mp4")])
        if not video_files:
            return JsonResponse({"error": "Hech qanday video topilmadi"}, status=404)
        
        audio_files = sorted([os.path.join(audio_dir, f) for f in os.listdir(audio_dir) if f.endswith(".mp3")])
        if not audio_files:
            return JsonResponse({"error": "Hech qanday audio topilmadi"}, status=404)
        
        audio_file = audio_files[0]  # Eng birinchi audio faylni olamiz
        
        # Audio uzunligini aniqlash
        probe = ffmpeg.probe(audio_file)
        audio_duration = float(probe['format']['duration'])
        
        # Har bir video uchun yangi uzunlikni hisoblash
        num_videos = len(video_files)
        new_video_duration = audio_duration / num_videos
        
        slow_videos = []
        for i, video in enumerate(video_files):
            slow_video = os.path.join(video_dir, f"slow_{i+1}.mp4")
            
            # Video asl uzunligini aniqlaymiz
            video_probe = ffmpeg.probe(video)
            video_duration = float(video_probe['format']['duration'])
            
            # Sekinlashtirish koeffitsienti
            slow_factor = new_video_duration / video_duration
            
            (
                ffmpeg
                .input(video)
                .filter("setpts", f"{slow_factor}*PTS")
                .output(slow_video)
                .run(overwrite_output=True)
            )
            slow_videos.append(slow_video)
        
        # Fayllarni birlashtirish uchun ro‘yxat yaratamiz
        concat_file = os.path.join(video_dir, "videos.txt")
        with open(concat_file, "w") as f:
            for video in slow_videos:
                f.write(f"file '{video}'\n")
        
        final_video = os.path.join(video_dir, "final_video.mp4")
        (
            ffmpeg
            .input(concat_file, format="concat", safe=0)
            .output(final_video, c="copy")
            .run(overwrite_output=True)
        )
        
        # Yakuniy video yaratish
        output_file = os.path.join(output_dir, f"{order_id}.mp4")
        os.makedirs(output_dir, exist_ok=True)
        
        video_stream = ffmpeg.input(final_video)
        audio_stream = ffmpeg.input(audio_file)
        (
            ffmpeg
            .output(video_stream, audio_stream, output_file, vcodec="copy", acodec="aac")
            .run(overwrite_output=True)
        )
        
        return JsonResponse({"message": "Video yaratildi", "file_path": output_file})


class TextToSpeechAPIView(APIView):
    def post(self, request, *args, **kwargs):
        order_id = request.data.get("order_id")
        gender = request.data.get("gender")
        text = request.data.get("text")
        
        if not order_id or not gender or not text:
            return JsonResponse({"error": "order_id, gender va text talab qilinadi"}, status=400)
        
        voices = {
            "m": "nPczCjzI2devNBz1zQrb",  # Brian
            "w": "XrExE9yKIg1WjnnlVkGX"  # Matilda
        }
        
        voice_id = voices.get(gender.lower())
        if not voice_id:
            return JsonResponse({"error": "Noto'g'ri gender qiymati"}, status=400)
        
        api_url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        headers = {
            "Content-Type": "application/json",
            "xi-api-key": "sk_09f4be641589db916c287d9cf61b26db215ca1ba61fd5d59"
        }
        data = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_name": "Brian" if gender.lower() == "m" else "Matilda"
        }
        
        response = requests.post(api_url, json=data, headers=headers)
        
        if response.status_code == 200:
            output_dir = f"/var/www/wellmay/audio/{order_id}"
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, "output_audio.mp3")
            
            with open(output_file, "wb") as f:
                f.write(response.content)
            
            # Audio uzunligini tekshirish va kerak bo'lsa tezlashtirish
            audio = AudioSegment.from_mp3(output_file)
            duration_seconds = len(audio) / 1000  # millisekundni sekundga o'tkazamiz
            
            if duration_seconds > 30:
                speed_factor = duration_seconds / 30.0
                audio = audio.speedup(playback_speed=speed_factor)
                audio.export(output_file, format="mp3")
            
            return JsonResponse({"message": "Audio saqlandi", "file_path": output_file})
        else:
            return JsonResponse({"error": "TTS xatosi", "details": response.text}, status=500)





class ImageToVideo(APIView):
    def post(self, request):
        image_url = request.data.get("image_url")
        order_id = request.data.get("order_id")
        prompt_text = "Identify key characters and objects in the image and animate natural, expressive movements that reflect their pose, facial expression, and the scene’s context. Movements should feel lifelike and fluid — avoid stiffness or repetition."
        "Ensure the animation fits a vertical 9:16 format. Reframe or extend the square image vertically to fill the full frame without blank borders. Use creative cropping or extend elements above and below, matching lighting, atmosphere, and scene integrity."
        "Vary motion intensity across the image to create liveliness. For characters, add subtle gestures like blinking, head or hand movement. For the environment, animate realistic motion: drifting light and shadow, breeze on trees or clothes, rippling water, or dust in the air."
        "Preserve the near-photorealistic, cinematic style of the original: soft natural lighting (e.g., golden hour), shallow depth of field, realistic textures, and natural color grading. Do not use cartoonish or artificial effects."

        if not image_url or not order_id:
            return Response({"error": "image_url va order_id kerak"}, status=status.HTTP_400_BAD_REQUEST)

        parsed_url = urlparse(image_url)
        filename = os.path.basename(parsed_url.path).split(".")[0] + ".mp4"

        output_dir = f"/var/www/wellmay/videos/{order_id}"
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, filename)

        # Runway API: video yaratish uchun POST so‘rov
        create_url = "https://api.dev.runwayml.com/v1/image_to_video"
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer key_94ef5e046fbbfae5fe16e524dd91824cb6b36c9f6272cb63c89658d23c37c73be0fdadf51ac7a92ff3f86a260ca026e434ecb796d3e8b3a7ac5f1fcbb5f1ba30",
            "X-Runway-Version": "2024-11-06"
        }
        data = {
            "promptImage": image_url,
            "seed": 4294967295,
            "model": "gen3a_turbo",
            "promptText": prompt_text,
            "watermark": False,
            "duration": 10,
            "ratio": "768:1280"
        }

        response = requests.post(create_url, json=data, headers=headers)
        if response.status_code != 200:
            return Response({"error": "Video yaratish so‘rov muvaffaqiyatsiz", "detail": response.text}, status=response.status_code)

        task_id = response.json().get("id")
        if not task_id:
            return Response({"error": "Task ID qaytmadi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Holatni tekshirish
        status_url = f"https://api.dev.runwayml.com/v1/tasks/{task_id}"
        while True:
            check_response = requests.get(status_url, headers=headers)
            if check_response.status_code != 200:
                return Response({"error": "Holatni tekshirib bo‘lmadi", "detail": check_response.text}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            task_data = check_response.json()
            if task_data.get("status") == "SUCCEEDED":
                video_url = task_data.get("output", [None])[0]
                if not video_url:
                    return Response({"error": "Outputda video URL topilmadi"}, status=500)
                break
            elif task_data.get("status") == "failed":
                return Response({"error": "Video yaratish muvaffaqiyatsiz"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            time.sleep(3)

        # Videoni yuklab olish
        video_response = requests.get(video_url, stream=True)
        with open(output_path, 'wb') as f:
            for chunk in video_response.iter_content(chunk_size=8192):
                f.write(chunk)

        return Response({
            "message": "Video yaratildi",
            "video_path": f"/videos/{order_id}/{filename}",
            "video_url": f"https://wellmay.uz/videos/{order_id}/{filename}"
        }, status=status.HTTP_201_CREATED)



class GenerateImageReelsView(APIView):
    def post(self, request):
        try:
            order_id = request.data.get("order_id")
            user_prompt = request.data.get("prompt")
            son = request.data.get("son")

            if not order_id or not user_prompt or not son:
                return Response({"error": "order_id, prompt va son talab qilinadi"}, status=status.HTTP_400_BAD_REQUEST)

            # Papkani yaratish
            output_dir = f"/var/www/wellmay/images/{order_id}"
            os.makedirs(output_dir, exist_ok=True)

            client = openai.OpenAI(api_key="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")

            # Asosiy kengaytirilgan prompt
            cinematic_prompt = ("""Based on the prepared post, create a prompt for a generative neural network (e.g., DALL·E 3) to generate a cinematic, ultra-realistic image in 1280×1280 resolution.

The image should visually match the topic and emotional tone of the post as closely as possible.

The style must be photorealistic or hyper-realistic, with no cartoonish or stylized aesthetics.

Characters (if present) must reflect the age, gender expression, appearance, clothing, emotional expression, and context described in the post. Their body language and positioning should communicate intent and narrative.

Ensure the scene has professional photographic composition: clear subject focus, appropriate depth of field, natural or cinematic lighting (e.g., golden hour, soft shadows, lens flare if applicable), and detailed textures (skin, fabric, environment).

Add details like camera angle, facial expressions, surroundings, and atmospheric elements (e.g., sunlight, reflections, weather, or motion blur) to make the image visually rich and emotionally engaging.

Use phrasing such as: "cinematic lighting", "high-end photography", "realistic depth and shadow", "professional-grade shot", "natural facial features and expressions", "expressive composition", "ultra-realistic textures and contrast."

Do not include any branding, text, or logos in the image.
The generated prompt must follow all ethical guidelines: no violence, discrimination, offensive stereotypes, unsafe behavior, or copyrighted elements.

                                The promt must be in English.""")
            full_prompt = f"{user_prompt.strip()}. {cinematic_prompt}"

            # Rasm yaratish
            response = client.images.generate(
                model="gpt-image-1",
                prompt=full_prompt,
                n=1,
                size="1024x1792",
                quality="high"
            )

            image_url = response.data[0].url
            image_response = requests.get(image_url)

            if image_response.status_code == 200:
                image = Image.open(BytesIO(image_response.content))
                output_path = os.path.join(output_dir, f"reels_{son}.jpg")
                image.save(output_path)
                image_path = f"/images/{order_id}/reels_{son}.jpg"

                return Response({"message": "Rasm muvaffaqiyatli yaratildi", "image_path": image_path}, status=status.HTTP_201_CREATED)
            else:
                return Response({"error": f"Rasmni yuklab olishda xatolik: {image_response.status_code}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except openai.BadRequestError as e:
            return Response({"error": f"API xatosi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Noma'lum xatolik: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class SenarioToPrompt(APIView):
    def post(self, request, *args, **kwargs):
        senario = request.data.get("senario")

        try:
            prompt_instruction = ("Based on the created script for Reels voiceover, taking into account its semantic structure, form a detailed text description for a generative neural network (e.g. DALL-E 3) in order to create a realistic vertical image with an aspect ratio of 9:16."
"The description should clearly convey the key points of the scenario. Take into account the style, atmosphere and emotion of the scenario."
"The image should match the topic of the post as much as possible and, most importantly, be visually cinematic, near-photorealistic image — exclude cartoonish stylisation."
"The gender, age, appearance, and composition of the characters or subjects in the generated image should reflect the context of the post and may differ from those in the attached image."
"Take into account all ethical standards: the image must not contain violence, offensive content, discrimination or violate copyright."
"The image must have the correct orientation of the horizon and objects, eliminating the possibility of flips. If there is a person in the frame, make sure they are upright: head at the top of the image, feet at the bottom. If there is text, it should be readable and properly orientated. If the image contains a landscape, architecture or interior, the space must be correctly orientated (sky at the top, ground at the bottom)."
"The promt must be clear, detailed and describe the desired scene, lighting, composition and key elements of the image and contain a clear 9:16 aspect ratio requirement."
"The promt must be in English."
"The result should be as relevant to the script as possible, so that when the image is animated (e.g. with lumalabs.ai) a coherent and harmonious video is created.")


            client = openai.Client(api_key="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")
            combined_message = f"{senario}\n\n{prompt_instruction}"

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": combined_message}]
            )

            gpt_response = completion.choices[0].message.content
            return Response({"prompts_photos": gpt_response}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)






class PostToPrompt(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        posts = request.data.get("posts")

    
        try:
            prompt_instruction = """Based on the prepared post, create a prompt for a generative neural network (e.g., DALL·E 3) to generate a cinematic, ultra-realistic image in 1280×1280 resolution.

The image should visually match the topic and emotional tone of the post as closely as possible.

The style must be photorealistic or hyper-realistic, with no cartoonish or stylized aesthetics.

Characters (if present) must reflect the age, gender expression, appearance, clothing, emotional expression, and context described in the post. Their body language and positioning should communicate intent and narrative.

Ensure the scene has professional photographic composition: clear subject focus, appropriate depth of field, natural or cinematic lighting (e.g., golden hour, soft shadows, lens flare if applicable), and detailed textures (skin, fabric, environment).

Add details like camera angle, facial expressions, surroundings, and atmospheric elements (e.g., sunlight, reflections, weather, or motion blur) to make the image visually rich and emotionally engaging.

Use phrasing such as: "cinematic lighting", "high-end photography", "realistic depth and shadow", "professional-grade shot", "natural facial features and expressions", "expressive composition", "ultra-realistic textures and contrast."

Do not include any branding, text, or logos in the image.
The generated prompt must follow all ethical guidelines: no violence, discrimination, offensive stereotypes, unsafe behavior, or copyrighted elements.The promt must be in English."""

            client = openai.Client(api_key="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")
            combined_message = f"{posts}\n\n{prompt_instruction}"

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": combined_message}]
            )

            gpt_response = completion.choices[0].message.content
            return Response({"for_image": gpt_response}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class PostToSenario(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        posts = request.data.get("posts")
        gender = request.data.get("gender")
        lang = request.data.get("lang")

        if not posts or not isinstance(posts, dict):
            return Response({"error": "Postlar noto‘g‘ri formatda yoki yo‘q"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            combined_text = "\n\n".join(posts.values())
            if gender == "m" and lang == "ru":
                prompt_instruction = ("""Из этих трех тем выбери одну, наиболее подходящую для видеоформата.

Затем на основе текста поста по этой теме (без добавления новых фактов и без генерации с нуля и с опорой на имеющуюся информацию) создай текст для озвучки Reels с помощью нейросети (например, ElevenLabs)  продолжительностью 30 секунд.

Текст должен быть адаптирован для живой и естественной речи, звучать динамично и легко восприниматься на слух. Учитывай, что текст должен быть рассчитан на точную продолжительность 30 секунд при озвучке в нормальном темпе (примерно 100 слов в минуту). Это значит, что итоговый текст должен содержать не более 50 слов.

Заголовок в начале не нужен. В тексте должно быть только то, что должна озвучить нейросеть.

Не используй эмодзи и символ �.

Структурируй текст для озвучки так, чтобы он плавно раскрывал основную мысль, удерживал внимание зрителя и мотивировал досмотреть видео до конца.
                                        При создании текста для озвучки учитывай, что повествование будет вестись от мужского лица, адаптируя стиль речи и интонации соответствующим образом.
                                                                            """)
            elif gender == "w" and lang == "ru":
                prompt_instruction = ("""Из этих трех тем выбери одну, наиболее подходящую для видеоформата.

Затем на основе текста поста по этой теме (без добавления новых фактов и без генерации с нуля и с опорой на имеющуюся информацию) создай текст для озвучки Reels с помощью нейросети (например, ElevenLabs)  продолжительностью 30 секунд.

Текст должен быть адаптирован для живой и естественной речи, звучать динамично и легко восприниматься на слух. Учитывай, что текст должен быть рассчитан на точную продолжительность 30 секунд при озвучке в нормальном темпе (примерно 100 слов в минуту). Это значит, что итоговый текст должен содержать не более 50 слов.

Заголовок в начале не нужен. В тексте должно быть только то, что должна озвучить нейросеть.

Не используй эмодзи и символ �.

Структурируй текст для озвучки так, чтобы он плавно раскрывал основную мысль, удерживал внимание зрителя и мотивировал досмотреть видео до конца.
                                        При создании текста для озвучки учитывай, что повествование будет вестись от женского лица, адаптируя стиль речи и интонации соответствующим образом.
                                      """)
            elif gender == "m" and lang == "en":
                prompt_instruction = ("""Choose one of the three topics that is best suited for video format.

Then, based on the post text for that topic (without adding new facts, without generating anything from scratch, and strictly relying on the existing information), create a voiceover script for a Reels video using a neural voice generator (like ElevenLabs) with a duration of 30 seconds.

The text should be adapted for natural and conversational speech, sound dynamic, and be easy to listen to. Note that the script should match an exact 30-second duration at a normal speaking pace (around 100 words per minute), which means the final text should contain no more than 50 words.

No title is needed at the beginning. The text should include only what the neural voice is meant to say.

Do not use emojis or the character �.

Structure the voiceover script to smoothly introduce the main idea, maintain the viewer's attention, and encourage them to watch the video until the end.

When creating the script, keep in mind that the narration will be from a male perspective, and adjust the tone and style accordingly.
                                      The content must be in English.""")
            elif gender == "w" and lang == "en":
                prompt_instruction = ("""Choose one of the three topics that is best suited for video format.

Then, based on the post text for that topic (without adding new facts, without generating anything from scratch, and strictly relying on the existing information), create a voiceover script for a Reels video using a neural voice generator (like ElevenLabs) with a duration of 30 seconds.

The text should be adapted for natural and conversational speech, sound dynamic, and be easy to listen to. Make sure it’s timed precisely for 30 seconds at a normal speaking pace (around 100 words per minute), meaning the final script should contain no more than 50 words.

No title at the beginning. The text must include only what the neural voice is meant to say.

Do not use emojis or the character �.

Structure the voiceover so it smoothly introduces the main idea, keeps the viewer’s attention, and motivates them to watch the video until the end.

When creating the script, keep in mind that the narration will be from a female perspective, and adapt the tone and style accordingly.
                                      The content must be in English.

""")

            client = openai.Client(api_key="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")
            combined_message = f"{combined_text}\n\n{prompt_instruction}"

            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": combined_message}]
            )

            gpt_response = completion.choices[0].message.content
            return Response({"senario": gpt_response}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        




class GenerateImageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            order_id = request.data.get("order_id")
            prompt = request.data.get("prompt")
            image_index = request.data.get("i")  # i ni olish

            if not order_id or not prompt or image_index is None:
                return Response({"error": "order_id, prompt va i talab qilinadi"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                image_index = int(image_index)
            except ValueError:
                return Response({"error": "i butun son bo'lishi kerak"}, status=status.HTTP_400_BAD_REQUEST)

            # Papkani yaratish
            output_dir = f"/var/www/wellmay/images/{order_id}"
            #output_dir = f"/images/{order_id}"
            os.makedirs(output_dir, exist_ok=True)

            client = openai.OpenAI(api_key="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")  # API kalitni yashirish tavsiya qilinadi!
            image_paths = []
            cinematic_prompt = (
                "A realistic, realistic image of a confident, charismatic individual standing at the center of a modern urban setting — such as a glass-walled office rooftop or an open-air conference terrace during golden hour. The person, in their mid-30s, gender-neutral presentation, wearing smart casual attire (dark blazer, light shirt, no tie), stands tall with open posture, making confident eye contact with a diverse group of people (varied in age, gender, and ethnicity) who are gathered around and attentively listening. The background shows a softly blurred skyline with warm, golden sunlight casting dramatic shadows and highlights. The atmosphere conveys trust, leadership, and attention. The lighting should be cinematic — warm tones with soft contrast and a subtle lens flare effect. Focus on expressive body language, natural facial expressions, and the unspoken influence of the central figure. No text or logos."
            )
            full_prompt = f"{prompt}. {cinematic_prompt}"


            # Bitta rasm yaratish
            response = client.images.generate(
                model="dall-e-3",
                prompt=full_prompt,
                n=1,
                size="1024x1024",
                quality="hd"
           )

            image_url = response.data[0].url
            image_response = requests.get(image_url)

            if image_response.status_code == 200:
                image = Image.open(BytesIO(image_response.content))
                output_path = os.path.join(output_dir, f"image_{image_index}.png")
                image.save(output_path)
                image_paths.append(f"/images/{order_id}/image_{image_index}.png")
            else:
                return Response({"error": f"Rasmni yuklab olishda xatolik: {image_response.status_code}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({"message": "Rasm muvaffaqiyatli yaratildi", "image_path": image_paths[0]}, status=status.HTTP_201_CREATED)

        except openai.BadRequestError as e:
            return Response({"error": f"API xatosi: {e}"}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Noma'lum xatolik: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





class TextToInstagramPostsView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user_text = request.data.get("text")
        gender = request.data.get("gender")
        lang = request.data.get("lang")
        
        if not user_text:
            return Response({"error": "Text kiritilmadi"}, status=status.HTTP_400_BAD_REQUEST)
        if gender not in ["m", "w"]:
            return Response({"error": "Gender noto'g'ri kiritildi"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Genderga qarab prompt ni tanlash
        if gender == "m" and lang == "ru":
            prompt_instruction = ("""Используя только обновленный уникальный на 100% текст (без добавления новых фактов, без генерации с нуля и с опорой на имеющуюся информацию), переработай его так, чтобы на выходе получился Instagram-пост по одной из наиболее популярных и актуальных тем, описанных в данном тексте (1500–2000 символов). 

Структурируй текст поста с разметкой по абзацам, сделай их увлекательными, легко читаемыми и вовлекающими. Умеренно используй эмодзи для визуального оформления и улучшения восприятия. Не используй символы "�" и "*".

В конце поста отдельным абзацем добавь 5–7 ключевых хэштегов, релевантных теме поста, чтобы улучшить их продвижение в Instagram.

                            При создании сценария учитывай, что повествование будет вестись от мужского лица, адаптируя стиль речи и интонации соответствующим образом.     """)
        elif gender == "w" and lang == "ru":
            prompt_instruction = ("""Используя только обновленный уникальный на 100% текст (без добавления новых фактов, без генерации с нуля и с опорой на имеющуюся информацию), переработай его так, чтобы на выходе получился Instagram-пост по одной из наиболее популярных и актуальных тем, описанных в данном тексте (1500–2000 символов). 

Структурируй текст поста с разметкой по абзацам, сделай их увлекательными, легко читаемыми и вовлекающими. Умеренно используй эмодзи для визуального оформления и улучшения восприятия. Не используй символы "?" и "*".

В конце поста отдельным абзацем добавь 5–7 ключевых хэштегов, релевантных теме поста, чтобы улучшить их продвижение в Instagram.

                            При создании сценария учитывай, что повествование будет вестись от женского лица, адаптируя стиль речи и интонации соответствующим образом.
""")
        elif gender == "m" and lang == "en":
            prompt_instruction = ("""Using only the updated, 100% unique text (without adding new facts, without generating from scratch, and based solely on the existing information), rework it into an Instagram post focused on one of the most popular and relevant topics described in the given text (1500–2000 characters).

Structure the post text with clear paragraph markup to make it engaging, easy to read, and captivating. Use emojis moderately to visually enhance and improve perception.

Do not use the symbols "?" or "*".

At the end of the post, add a separate paragraph with 5–7 key hashtags relevant to the post topic to boost its visibility on Instagram.
                                  
When creating the narrative, keep in mind that it will be told from a male perspective, adapting the tone and style accordingly.
                                  The content must be in English.""")
        
        elif gender == "w" and lang == "en":
            prompt_instruction = ("""Using only the updated, 100% unique text (without adding new facts, without generating from scratch, and based solely on the existing information), rework it into an Instagram post focused on one of the most popular and relevant topics described in the given text (1500–2000 characters).

Structure the post text with clear paragraph markup to make it engaging, easy to read, and captivating. Use emojis moderately to visually enhance and improve perception.

Do not use the symbols "?" or "*".

At the end of the post, add a separate paragraph with 5–7 key hashtags relevant to the post topic to boost its visibility on Instagram.

When creating the narrative, keep in mind that it will be told from a female perspective, and adapt the tone and writing style accordingly.
                                  The content must be in English.""")
        
        # Foydalanuvchi tomonidan yuborilgan matn va prompt ni birlashtiramiz
        combined_message = f"{user_text}\n\n{prompt_instruction}"
        
        # OpenAI mijozini API kaliti bilan ishga tushiramiz (kalitni xavfsiz saqlash tavsiya etiladi)
        client = OpenAI(api_key="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")
        
        try:
            completion = client.chat.completions.create(
                model="gpt-4o-mini",
                store=True,
                messages=[{"role": "user", "content": combined_message}]
            )
            # Javobni olish
            gpt_response = completion.choices[0].message.content
            
            
            return Response({"post": gpt_response}, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)





#Create Order 
class CheckAndCreateOrder(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        user = request.user  

        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return Response({"error": "Foydalanuvchi topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        if user_profile.free or user_profile.premium:
            if user_profile.reels >= 1 and user_profile.post >= 3:
                user_profile.reels -= 1
                user_profile.post -= 3
                user_profile.image -= 3

                if user_profile.reels == 0 or user_profile.post == 0:
                    user_profile.premium = False
                    user_profile.free = False
                user_profile.save()

                order = Orders.objects.create(user=user)
                return Response({"order_id": str(order.order_id)}, status=status.HTTP_200_OK)
            else:
                return Response({"error": "Balansingizda yetarli reels yoki post yo'q."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({"error": "Premium rejasi yo'q yoki tugagan."}, status=status.HTTP_400_BAD_REQUEST)


class AudioToTextView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logger.info("POST request keldi")
        order_id = request.data.get("order_id")
        user = request.user

        logger.debug(f"User: {user}")
        logger.debug(f"Order ID: {order_id}")

        if not user or not order_id:
            logger.warning("User yoki order_id yo'q")
            return Response({"error": "user_id va order_id kiritilishi shart"}, status=status.HTTP_400_BAD_REQUEST)
        
        file_path_webm = f"/app/musics/{order_id}.webm"
        file_path_mp4 = f"/app/musics/{order_id}.mp4"

        logger.info(f"Tekshirilmoqda: {file_path_webm}")
        if os.path.exists(file_path_webm):
            file_path = file_path_webm
            logger.info(f".webm fayl topildi: {file_path}")
        elif os.path.exists(file_path_mp4):
            file_path = file_path_mp4
            logger.info(f".mp4 fayl topildi: {file_path}")
        else:
            logger.error("Fayl topilmadi")
            return Response({"error": "Fayl mavjud emas"}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            logger.info("Transkripsiya jarayoni boshlandi...")
            result = model.transcribe(file_path, language='ru')
            logger.info("Transkripsiya yakunlandi")
            logger.debug(f"Natija: {result['text']}")
            return Response({"text": result["text"]}, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception("Transkripsiya vaqtida xatolik yuz berdi")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
     class YouTubeToMP3View(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        video_url = request.data.get('video_url')
        orderid = request.data.get('order_id')
        user = request.user

        logger.info("POST so‘rovi kelib tushdi: YouTubeToMP3View")
        logger.info(f"User: {user}, Video URL: {video_url}, Order ID: {orderid}")

        # Foydalanuvchini tekshiramiz
        try:
            user_profile = UserProfile.objects.get(user=user)
            logger.info(f"UserProfile topildi: {user_profile.id}")
        except UserProfile.DoesNotExist:
            logger.error("Foydalanuvchi profili topilmadi")
            return Response({"error": "Foydalanuvchi topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        # Yuklab olish jarayoni
        try:
            order_id = download_audio(video_url, orderid)

            if order_id:
                logger.info(f"Audio muvaffaqiyatli yuklab olindi: {order_id}")
                return Response({"order_id": str(order_id)}, status=status.HTTP_200_OK)
            
            logger.error("Faylni yuklab bo‘lmadi")
            return Response({"error": "Faylni yuklab bo‘lmadi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            logger.exception(f"MP3 yuklashda xatolik: {str(e)}")
            return Response({"error": "Ichki xatolik yuz berdi"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


#SIGN IN 
class UserCreateAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserCreateSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Foydalanuvchi muvaffaqiyatli yaratildi."}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

#LOGIN
class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = request.data.get('email')
        password = request.data.get('password')

        if not identifier or not password:
            return Response({'error': 'Email and password required'}, status=400)

        try:
            user = CustomUser.objects.get(email=identifier)
        except CustomUser.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)

        if not user.check_password(password):
            return Response({'error': 'Incorrect password'}, status=401)

        if not user.is_active:
            return Response({'error': 'User is inactive'}, status=403)

        # JWT tokenlar
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        return Response({
            'message': 'Login successful',
            'access': access_token,
            'refresh': str(refresh),
            'user': {
                'uuid': str(user.uuid),
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
        }, status=200)
