
from django.urls import path
from .views import LastFourOrdersView,LoginView,VideosToReels,ImageToVideo,TextToSpeechAPIView,GenerateImageReelsView,PostToPrompt,SenarioToPrompt,UserCreateAPIView,YouTubeToMP3View,CheckAndCreateOrder,TextToInstagramPostsView,GenerateImageView,PostToSenario


urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='jwt-login'),
    path('auth/signin/', UserCreateAPIView.as_view(), name='sign-in'),
    path('convert/mp3/', YouTubeToMP3View.as_view(), name='music'),
    path('check/create/', CheckAndCreateOrder.as_view(), name='check-status-order'),
    path('convert/post/', TextToInstagramPostsView.as_view(), name='post'),
    path('convert/image-post/', GenerateImageView.as_view(), name='image-post'),
    path('convert/senario/', PostToSenario.as_view(), name='senario'),
    path('convert/post-prompt/', PostToPrompt.as_view(), name='prompt-post'),
    path('convert/senario-prompt/', SenarioToPrompt.as_view(), name='senario-prompt'),
    path('convert/image-video/', GenerateImageReelsView.as_view(), name='image-video'),
    path('convert/video/', ImageToVideo.as_view(), name='video'),
    path('convert/speech/', TextToSpeechAPIView.as_view(), name='speech'),
    path('convert/reels/', VideosToReels.as_view(), name='reels'),    
    path('order/last4/', LastFourOrdersView.as_view(), name='last4'),    
]
