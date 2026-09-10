from django.urls import path

from .sse import stream_conversation
from .views import ConversationDetailView, ConversationListCreateView, SendMessageView

urlpatterns = [
    path("", ConversationListCreateView.as_view(), name="conversation-list-create"),
    path("<int:pk>/", ConversationDetailView.as_view(), name="conversation-detail"),
    path("<int:pk>/messages/", SendMessageView.as_view(), name="conversation-send-message"),
    path("<int:pk>/stream/", stream_conversation, name="conversation-stream"),
]
