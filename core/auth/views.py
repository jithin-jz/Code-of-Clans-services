from urllib.parse import urlencode
from drf_spectacular.utils import extend_schema, OpenApiTypes
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from rest_framework import status, serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import AnonRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView

from .throttles import AuthRateThrottle, SensitiveOperationThrottle

from users.serializers import UserSerializer
from .serializers import (
    RefreshTokenSerializer,
    AdminLoginSerializer,
    OAuthCodeSerializer,
    OAuthURLSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
)
from .services import AuthService
from .utils import generate_access_token, decode_token, generate_tokens


def _set_auth_cookies(response, access_token: str, refresh_token: str | None = None):
    response.set_cookie(
        settings.JWT_ACCESS_COOKIE_NAME,
        access_token,
        httponly=True,
        secure=settings.JWT_COOKIE_SECURE,
        samesite=settings.JWT_COOKIE_SAMESITE,
        max_age=settings.JWT_ACCESS_TOKEN_LIFETIME,
        path="/",
    )
    if refresh_token:
        response.set_cookie(
            settings.JWT_REFRESH_COOKIE_NAME,
            refresh_token,
            httponly=True,
            secure=settings.JWT_COOKIE_SECURE,
            samesite=settings.JWT_COOKIE_SAMESITE,
            max_age=settings.JWT_REFRESH_TOKEN_LIFETIME,
            path="/",
        )


def _clear_auth_cookies(response):
    response.delete_cookie(settings.JWT_ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME, path="/")


def _auth_success_response(request, user, result):
    payload = {
        "access_token": result["access_token"],
        "refresh_token": result["refresh_token"],
        "user": UserSerializer(user, context={"request": request}).data,
    }
    response = Response(payload, status=status.HTTP_200_OK)
    _set_auth_cookies(
        response,
        access_token=result["access_token"],
        refresh_token=result["refresh_token"],
    )
    return response


# --- OAuth Views ---
# These views handle the HTTP layer of OAuth: redirects and callbacks.
# All business logic is delegated to AuthService.


class GitHubAuthURLView(APIView):
    """
    Step 1 of GitHub OAuth: Get the redirect URL.
    Returns: { "url": "https://github.com/login/oauth/authorize?..." }
    """

    permission_classes = [AllowAny]
    throttle_classes = []
    serializer_class = OAuthURLSerializer

    def get(self, request):
        state = request.query_params.get("state")
        params = {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": settings.GITHUB_REDIRECT_URI,
            "scope": "user:email",  # Request email access
        }
        if state:
            params["state"] = state

        url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
        return Response({"url": url}, status=status.HTTP_200_OK)


class GitHubCallbackView(APIView):
    """
    Step 2 of GitHub OAuth: Handle the callback code.
    Accepts: { "code": "..." }
    Returns: { "access_token": "...", "user": {...} }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]
    serializer_class = OAuthCodeSerializer

    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response(
                {"error": "Authorization code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delegate to Service Layer
        user, result = AuthService.handle_oauth_login("github", code)

        if not user:
            # Login Failed (result contains error dict)
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return _auth_success_response(request, user, result)


class GoogleAuthURLView(APIView):
    """Return the Google OAuth authorization URL."""

    permission_classes = [AllowAny]
    throttle_classes = []
    serializer_class = OAuthURLSerializer

    def get(self, request):
        state = request.query_params.get("state")
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",
            "access_type": "offline",
            "prompt": "select_account",
        }
        if state:
            params["state"] = state

        url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        return Response({"url": url}, status=status.HTTP_200_OK)


class GoogleCallbackView(APIView):
    """Handle Google OAuth callback."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]
    serializer_class = OAuthCodeSerializer

    def post(self, request):
        code = request.data.get("code")
        if not code:
            return Response(
                {"error": "Authorization code is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, result = AuthService.handle_oauth_login("google", code)

        if not user:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return _auth_success_response(request, user, result)


# --- General User Views ---


class RefreshTokenView(APIView):
    """Refresh the access token using a refresh token."""

    permission_classes = [AllowAny]
    serializer_class = RefreshTokenSerializer

    def post(self, request):
        token = request.data.get("refresh_token") or request.COOKIES.get(
            settings.JWT_REFRESH_COOKIE_NAME
        )
        if not token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = decode_token(token)

        if not payload:
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if payload.get("type") != "refresh":
            return Response(
                {"error": "Invalid token type"}, status=status.HTTP_401_UNAUTHORIZED
            )

        try:
            user = User.objects.get(id=payload["user_id"])
        except User.DoesNotExist:
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {"error": "User account is disabled."}, status=status.HTTP_403_FORBIDDEN
            )

        new_access_token = generate_access_token(user)

        response = Response(
            {
                "access_token": new_access_token,
                "user": UserSerializer(user, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )
        _set_auth_cookies(response, access_token=new_access_token)
        return response


class LogoutView(APIView):
    """Logout the user (client should delete tokens)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={200: OpenApiTypes.OBJECT},
        description="Logout the user. Client should discard tokens.",
    )
    def post(self, request):
        # In a stateless JWT system, logout is handled client-side
        # We clear auth cookies as well.
        response = Response(
            {"message": "Successfully logged out"}, status=status.HTTP_200_OK
        )
        _clear_auth_cookies(response)
        return response


class DeleteAccountView(APIView):
    """View to delete the user account."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [SensitiveOperationThrottle]

    @extend_schema(
        request=None,
        responses={200: OpenApiTypes.OBJECT},
        description="Delete the user account permanently.",
    )
    def delete(self, request):
        user = request.user
        user.delete()
        return Response(
            {"message": "Account deleted successfully"}, status=status.HTTP_200_OK
        )


# --- Admin Views ---


class AdminLoginView(APIView):
    """Admin login view."""

    permission_classes = [AllowAny]
    throttle_classes = [AuthRateThrottle]
    serializer_class = AdminLoginSerializer

    def post(self, request):
        serializer = AdminLoginSerializer(
            data=request.data, context={"request": request}
        )

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = serializer.validated_data["user"]
        tokens = generate_tokens(user)

        return _auth_success_response(request, user, tokens)


# --- OTP Views ---


class OTPRequestView(APIView):
    """
    Step 1 of Email OTP Login: Request a One-Time Password.
    Accepts: { "email": "user@example.com" }
    """

    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle]
    throttle_scope = "otp"
    serializer_class = OTPRequestSerializer

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        try:
            AuthService.request_otp(email)
        except ValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return Response({"error": message}, status=status.HTTP_429_TOO_MANY_REQUESTS)

        return Response({"message": "OTP sent successfully"}, status=status.HTTP_200_OK)


class OTPVerifyView(APIView):
    """
    Step 2 of Email OTP Login: Verify the One-Time Password.
    Accepts: { "email": "user@example.com", "otp": "123456" }
    Returns: { "access_token": "...", "user": {...} }
    """

    permission_classes = [AllowAny]
    throttle_classes = [SensitiveOperationThrottle]
    serializer_class = OTPVerifySerializer

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]

        user, result = AuthService.verify_otp(email, otp)

        if not user:
            return Response(result, status=status.HTTP_400_BAD_REQUEST)

        return _auth_success_response(request, user, result)
