from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Order
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import requests
# import aiohttp
from rest_framework import status as drf_status
import uuid
from .serializers import OrderResponseSerializer,OrderSerializer,UpdateOrderBankSerializer
from rest_framework.permissions import IsAuthenticated
from users.models import UserProfile

username = "WELLMAYBOTLMT*USD-api"
password = "WellmayLSD429GI!"



class UpdateOrderStatusView(APIView):
    def post(self, request):
        order_bank_uuid = request.data.get("order_bank_uuid")

        if not order_bank_uuid:
            return Response({"error": "order_bank_uuid is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(order_bank_uuid=uuid.UUID(order_bank_uuid))
            order.is_active = False
            order.save()
            return Response({"message": "Order status updated to False."}, status=status.HTTP_200_OK)
        except Order.DoesNotExist:
            return Response({"error": "Order not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError:
            return Response({"error": "Invalid UUID format."}, status=status.HTTP_400_BAD_REQUEST)



class PaymentVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        order_id = request.data.get('order_id')
        errors = {}

        if not order_id:
            return Response({'detail': 'order_id majburiy.'}, status=drf_status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(order_bank_uuid=order_id, user=user)
            if order.status:
                return Response({'detail': 'Order allaqachon aktivlashtirilgan.'}, status=drf_status.HTTP_400_BAD_REQUEST)
        except Order.DoesNotExist:
            return Response({'detail': 'Order topilmadi.'}, status=drf_status.HTTP_404_NOT_FOUND)

        # 2-qadam: Tashqi to'lov statusini tekshirish
        try:
            payment_response = requests.get(
                "https://securepayments.berekebank.kz/payment/rest/getOrderStatus.do",
                params={
                    "userName": 'your_username',  # <-- o'zgartiring
                    "password": 'your_password',  # <-- o'zgartiring
                    "orderId": str(order.order_bank_uuid)
                },
                timeout=10
            )
            payment_response.raise_for_status()
            data = payment_response.json()
        except Exception as e:
            errors['payment_api'] = f"To'lov tekshiruvda xatolik: {str(e)}"
            return Response({'errors': errors}, status=drf_status.HTTP_502_BAD_GATEWAY)

        # 3-qadam: Javobni tekshirish
        if data.get("OrderStatus") == 2:
            try:
                user_profile = UserProfile.objects.get(user=user)

                if order.premium_name == 'Junior':
                    user_profile.post += 15
                    user_profile.image += 15
                    user_profile.reels += 5
                elif order.premium_name == 'Middle':
                    user_profile.post += 45
                    user_profile.image += 45
                    user_profile.reels += 15
                elif order.premium_name == 'Senior':
                    user_profile.post += 90
                    user_profile.image += 90
                    user_profile.reels += 30
                else:
                    errors['premium_name'] = 'Noto‘g‘ri premium nomi.'

                user_profile.premium = True
                user_profile.save()

                order.status = True
                order.is_active = False
                order.save()

                return Response({'detail': 'Muvaffaqiyatli aktivlashtirildi.'}, status=drf_status.HTTP_200_OK)

            except UserProfile.DoesNotExist:
                errors['user_profile'] = 'User profili topilmadi.'
        else:
            errors['order_status'] = f"OrderStatus muvaffaqiyatli emas: {data.get('OrderStatus')}"

        return Response({'errors': errors}, status=drf_status.HTTP_400_BAD_REQUEST)






class BerekeCreateOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        order_number = request.data.get("orderNumber")
        usd_amount = request.data.get("usd_amount")

        if not all([order_number, usd_amount]):
            return Response(
                {"error": "orderNumber va usd_amount majburiy"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            usd_amount = int(usd_amount)
        except ValueError:
            return Response(
                {"error": "usd_amount raqam bo'lishi kerak."},
                status=status.HTTP_400_BAD_REQUEST
            )

        print(f"[Bereke Order] user={user.id}, amount=${usd_amount}")


        api_url = "https://securepayments.berekebank.kz/payment/rest/register.do"
        data = {
            'amount': usd_amount,
            'currency': 840,
            'userName': username,
            'password': password,
            'returnUrl': 'https://wellmay.uz/success/',
            'description': f'Payment for ${usd_amount}',
            'language': 'ru',
            'orderNumber': order_number
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
        }

        try:
            response = requests.post(api_url, headers=headers, data=data, timeout=30)
            print(f"Bereke API javobi: {response.text}")

            json_data = response.json()

            if 'formUrl' in json_data and 'orderId' in json_data:
                try:
                    order = Order.objects.get(user=user, order_bot=order_number)
                    order.order_bank_uuid = json_data['orderId']
                    order.save()
                except Order.DoesNotExist:
                    return Response(
                        {"error": "Tegishli order topilmadi"},
                        status=status.HTTP_404_NOT_FOUND
                    )

                return Response({
                    "form_url": json_data['formUrl'],
                    "order_id": json_data['orderId']
                }, status=status.HTTP_200_OK)
            else:
                return Response({"error": json_data}, status=status.HTTP_400_BAD_REQUEST)

        except requests.RequestException as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class UpdateOrderBankAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = UpdateOrderBankSerializer(data=request.data)
        if serializer.is_valid():
            order_bot = serializer.validated_data['order_bot']
            order_bank_uuid = serializer.validated_data['order_bank_uuid']
            user = request.user

            try:
                # Foydalanuvchiga tegishli mos orderni topamiz
                order = Order.objects.get(user=user, order_bot=order_bot)
                order.order_bank_uuid = order_bank_uuid
                order.save()
                return Response({"detail": "Order bank ma'lumotlari saqlandi."}, status=status.HTTP_200_OK)
            except Order.DoesNotExist:
                return Response({"detail": "Order topilmadi."}, status=status.HTTP_404_NOT_FOUND)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# Create your views here.
class CreateOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        # Avvalgi tugallanmagan (status=False) va faol (is_active=True) order borligini tekshiramiz
        existing_orders = Order.objects.filter(user=user, is_active=True, status=False)

        if existing_orders.exists():
            existing_orders_serializer = OrderResponseSerializer(existing_orders, many=True)
            return Response(
                {
                    "detail": "Sizda hali tugallanmagan order mavjud.",
                    "orders": existing_orders_serializer.data
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Yangi order yaratamiz
        data = request.data.copy()
        data['user'] = user.id  # serializer uchun user id kerak bo'ladi
        serializer = OrderSerializer(data=data)

        if serializer.is_valid():
            order = serializer.save()
            response_serializer = OrderResponseSerializer(order)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)