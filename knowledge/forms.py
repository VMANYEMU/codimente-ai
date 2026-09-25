from django import forms

from .models import Document


ALLOWED_EXTENSIONS = [".pdf", ".docx", ".txt"]

MAX_UPLOAD_MB = 20


class DocumentUploadForm(forms.ModelForm):

    class Meta:
        model = Document
        fields = ["title", "file"]

        widgets = {
            "title": forms.TextInput(
                attrs={
                    "placeholder": (
                        "Optional — defaults to the file name"
                    )
                }
            ),
        }

    def clean_file(self):

        uploaded_file = self.cleaned_data.get("file")

        if not uploaded_file:
            return uploaded_file

        # Extension check (matches the extractor's
        # supported formats).

        import os

        extension = os.path.splitext(
            uploaded_file.name
        )[1].lower()

        if extension not in ALLOWED_EXTENSIONS:

            raise forms.ValidationError(
                "Unsupported file type "
                f"\"{extension}\". Allowed: "
                + ", ".join(ALLOWED_EXTENSIONS)
            )

        # Size check.

        max_bytes = MAX_UPLOAD_MB * 1024 * 1024

        if uploaded_file.size > max_bytes:

            raise forms.ValidationError(
                f"File exceeds the {MAX_UPLOAD_MB} MB "
                "upload limit."
            )

        return uploaded_file

    def clean_title(self):

        title = self.cleaned_data.get("title")

        if not title:

            uploaded_file = self.cleaned_data.get("file")

            if uploaded_file:

                import os

                title = os.path.splitext(
                    uploaded_file.name
                )[0]

        return title
