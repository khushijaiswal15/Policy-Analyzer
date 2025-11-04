from django.db import models
from django.utils import timezone

# 🔍 Stores extracted policy analysis from PDF or URL
class PolicyAnalysis(models.Model):
    title = models.CharField(max_length=255)
    date = models.CharField(max_length=100)
    summary = models.TextField()
    affected = models.TextField()
    sector_impacts = models.JSONField()
    most_sector = models.CharField(max_length=100)
    most_text = models.TextField()

    # Source data
    pdf_file = models.FileField(upload_to='uploads/', null=True, blank=True)
    source_url = models.URLField(null=True, blank=True)
    uploaded_from = models.CharField(
        max_length=10,
        choices=[('file', 'File'), ('url', 'URL')],
        default='file'
    )

    def __str__(self):
        return f"{self.title} ({self.date})"


# 🌐 Keeps track of URL crawling jobs
class URLExtractionJob(models.Model):
    url = models.URLField(max_length=5000)  # ✅ Supports very long URLs
    status = models.CharField(
        max_length=100,
        choices=[
            ('in_progress', 'In Progress'),
            ('paused', 'Paused'),
            ('completed', 'Completed'),
        ],
        default='in_progress'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Job #{self.id} - {self.url}"


# 📄 Links extracted from a crawling job
class PDFLink(models.Model):
    job = models.ForeignKey(URLExtractionJob, on_delete=models.CASCADE)
    link = models.URLField(max_length=6048)
    link_type = models.CharField(
        max_length=10,
        choices=[('pdf', 'PDF'), ('html', 'HTML')],
        default='html'
    )
    uploaded_at = models.DateTimeField(default=timezone.now)

    # ✅ Track whether this link has been processed
    extracted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('job', 'link')  # ✅ Prevent duplicate links per job

    def __str__(self):
        return f"[{self.link_type.upper()}] {self.link}"


# 📝 Stores extracted text from PDFLink (one per link)
class ExtractedText(models.Model):
    link = models.OneToOneField(PDFLink, on_delete=models.CASCADE, related_name='extracted_text')
    text = models.TextField()
    extracted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Text from: {self.link.link}"
