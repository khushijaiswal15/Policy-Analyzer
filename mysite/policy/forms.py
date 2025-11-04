from django import forms

class UploadPDFForm(forms.Form):
    pdf = forms.FileField()

class URLUploadForm(forms.Form):
    url = forms.URLField(label="Website URL", required=True)
