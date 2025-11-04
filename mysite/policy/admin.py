from django.contrib import admin
from .models import PolicyAnalysis, URLExtractionJob, PDFLink

# 📄 Admin config for extracted policy data
@admin.register(PolicyAnalysis)
class PolicyAnalysisAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'uploaded_from', 'source_url')
    search_fields = ('title', 'summary', 'affected')
    list_filter = ('uploaded_from',)
    ordering = ('-date',)


# 🌐 Admin config for URL crawling jobs
@admin.register(URLExtractionJob)
class URLExtractionJobAdmin(admin.ModelAdmin):
    list_display = ('url', 'status', 'created_at')
    search_fields = ('url',)
    list_filter = ('status',)
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)


# 🔗 Admin config for extracted links
@admin.register(PDFLink)
class PDFLinkAdmin(admin.ModelAdmin):
    list_display = ('link', 'link_type', 'job', 'uploaded_at')
    search_fields = ('link',)
    list_filter = ('link_type', 'uploaded_at')
    date_hierarchy = 'uploaded_at'
    ordering = ('-uploaded_at',)
