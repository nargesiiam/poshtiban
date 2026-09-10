from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import RegisterSerializer, UserSerializer


class RegisterView(generics.CreateAPIView):
    """
    ثبت‌نام باز است — تنها endpointـی که عمداً AllowAny دارد.
    این استثنا صریح است، نه پیش‌فرض فراموش‌شده.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer


class LoginView(TokenObtainPairView):
    """
    ورود استاندارد JWT (simplejwt) — access و refresh token برمی‌گرداند.
    منطق خاصی اینجا نیست، فقط برای consistency مسیرِ /api/auth/login/ را می‌دهیم.
    """
    permission_classes = [permissions.AllowAny]


class MeView(APIView):
    """
    کاربر جاری را برمی‌گرداند — همیشه از request.user، هرگز از پارامتر ورودی.
    این یک تمرین کوچک اما مهم از همان قانونی است که در کل پروژه رعایت می‌شود:
    هویتِ «من کی‌ام» همیشه از توکن می‌آید، نه از چیزی که کلاینت ادعا می‌کند.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
