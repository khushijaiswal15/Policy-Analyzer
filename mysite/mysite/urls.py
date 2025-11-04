from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),          # Django admin
    path('', include('policy.urls')),         # Your main app
]

# Serve uploaded files (PDFs etc.) in development
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
