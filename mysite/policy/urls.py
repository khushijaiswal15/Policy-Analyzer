from django.urls import path
from django.views.decorators.http import require_POST
from . import views

urlpatterns = [
    path('', views.upload_pdf, name='upload_pdf'),
    path('upload-url/', views.upload_from_url, name='upload_from_url'),

    path('monitor/<int:job_id>/', views.monitor_extraction, name='monitor_extraction'),
    path('pause/<int:job_id>/', views.pause_job, name='pause_job'),
    path('resume/<int:job_id>/', views.resume_job, name='resume_job'),

    path('policy/<int:policy_id>/', views.view_policy, name='view_policy'),
    path('delete/<int:policy_id>/', views.delete_policy, name='delete_policy'),

    path('view-saved/', views.view_saved, name='view_saved'),
    path('view-file-uploads/', views.view_uploaded_pdfs, name='view_uploaded_pdfs'),
    path('view-url-uploads/', views.view_url_pdfs, name='view_url_pdfs'),

    path('delete-pdf-link/<int:link_id>/', views.delete_pdf_link, name='delete_pdf_link'),

    path('extract-next-100/', require_POST(views.extract_next_100_links), name='extract_next_100'),

    path('extracted-texts/', views.view_extracted_texts, name='view_extracted_texts'),
    path('view-extracted-text/<int:pk>/', views.view_text_detail, name='view_text_detail'),
    path('delete-extracted-text/<int:pk>/', views.delete_extracted_text, name='delete_extracted_text'),
]
