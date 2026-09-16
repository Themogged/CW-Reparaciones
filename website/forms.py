from collections import OrderedDict

from django import forms
from django.utils import timezone

from .models import Service, ServiceRequest


class ServiceRequestForm(forms.ModelForm):
    """Recopila información preliminar; no representa un diagnóstico técnico."""

    ISSUE_CHOICES = (
        ("", "Selecciona una opción"),
        ("No enciende", "No enciende"),
        ("Hace ruido", "Hace ruido"),
        ("No funciona correctamente", "No funciona correctamente"),
        ("Presenta fuga", "Presenta fuga"),
        ("Pierde potencia", "Pierde potencia"),
        ("Otro", "Otro"),
    )

    STEP_FIELDS = OrderedDict(
        (
            (1, ("service", "equipment")),
            (2, ("brand", "model")),
            (3, ("issue", "frequency", "description")),
            (4, ("diagnostic_media",)),
            (5, ("municipality", "sector", "address")),
            (
                6,
                (
                    "name",
                    "whatsapp",
                    "phone",
                    "email",
                    "contact_preference",
                    "privacy_accepted",
                ),
            ),
            (7, ("preferred_date", "preferred_time")),
        )
    )

    issue = forms.ChoiceField(choices=ISSUE_CHOICES, label="Problema")
    privacy_accepted = forms.BooleanField(
        required=True,
        label="Acepto el tratamiento de mis datos para atender esta solicitud.",
        error_messages={
            "required": "Debes aceptar el aviso de privacidad para continuar."
        },
    )
    website = forms.CharField(
        required=False,
        label="",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "off",
                "tabindex": "-1",
                "aria-hidden": "true",
            }
        ),
    )

    class Meta:
        model = ServiceRequest
        fields = (
            "service",
            "equipment",
            "brand",
            "model",
            "issue",
            "frequency",
            "description",
            "diagnostic_media",
            "name",
            "phone",
            "whatsapp",
            "email",
            "municipality",
            "sector",
            "address",
            "preferred_date",
            "preferred_time",
            "contact_preference",
            "privacy_accepted",
            "source",
            "utm_source",
            "utm_medium",
            "utm_campaign",
            "utm_content",
            "utm_term",
        )
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 5,
                    "maxlength": 3000,
                    "placeholder": "Describe qué sucede y cualquier detalle útil.",
                }
            ),
            "preferred_date": forms.DateInput(attrs={"type": "date"}),
            "preferred_time": forms.TimeInput(attrs={"type": "time"}),
            "diagnostic_media": forms.ClearableFileInput(
                attrs={
                    "accept": "image/jpeg,image/png,image/webp,video/mp4",
                    "data-max-image-bytes": "8388608",
                    "data-max-video-bytes": "20971520",
                }
            ),
            "source": forms.HiddenInput(),
            "utm_source": forms.HiddenInput(),
            "utm_medium": forms.HiddenInput(),
            "utm_campaign": forms.HiddenInput(),
            "utm_content": forms.HiddenInput(),
            "utm_term": forms.HiddenInput(),
        }
        error_messages = {
            "equipment": {"required": "Indica qué equipo presenta el problema."},
            "description": {"required": "Cuéntanos brevemente qué sucede."},
            "name": {"required": "Ingresa tu nombre."},
            "whatsapp": {"required": "Ingresa un número de WhatsApp."},
            "municipality": {"required": "Indica tu municipio para consultar cobertura."},
        }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.filter(
            is_active=True, category__is_active=True
        ).select_related("category")
        self.fields["service"].required = False
        self.fields["service"].empty_label = "Servicio por definir"
        self.fields["whatsapp"].required = True
        self.fields["municipality"].required = True
        self.fields["contact_preference"].required = False
        self.fields["contact_preference"].initial = ServiceRequest.ContactPreference.WHATSAPP
        self.fields["contact_preference"].widget = forms.HiddenInput()
        self.fields["frequency"].required = False
        self.fields["frequency"].initial = ServiceRequest.Frequency.UNKNOWN
        self.fields["diagnostic_media"].help_text = (
            "Puedes adjuntar una foto para ayudarnos a entender mejor el problema. "
            "JPEG, PNG o WebP hasta 8 MB; MP4 hasta 20 MB."
        )
        self.fields["whatsapp"].help_text = "Número principal para responder tu solicitud."
        self.fields["phone"].help_text = "Opcional: número alternativo para llamadas."
        self.fields["email"].help_text = "Opcional."
        self.fields["preferred_date"].help_text = "La fecha solicitada no representa una cita confirmada."
        self.fields["brand"].help_text = "Opcional. Indica la marca que aparece en tu equipo."

        for field_name, field in self.fields.items():
            if field_name not in {
                "privacy_accepted",
                "diagnostic_media",
                "source",
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_content",
                "utm_term",
            }:
                field.widget.attrs.setdefault("autocomplete", "off")

        self.fields["name"].widget.attrs["autocomplete"] = "name"
        self.fields["phone"].widget.attrs.update(
            {"autocomplete": "tel", "inputmode": "tel"}
        )
        self.fields["whatsapp"].widget.attrs.update(
            {"autocomplete": "tel", "inputmode": "tel"}
        )
        self.fields["email"].widget.attrs.update(
            {"autocomplete": "email", "inputmode": "email"}
        )
        self.fields["address"].widget.attrs["autocomplete"] = "street-address"

    def clean_preferred_date(self):
        value = self.cleaned_data.get("preferred_date")
        if value and value < timezone.localdate():
            raise forms.ValidationError("Selecciona una fecha de hoy en adelante.")
        return value

    def clean_frequency(self):
        return self.cleaned_data.get("frequency") or ServiceRequest.Frequency.UNKNOWN

    def clean_website(self) -> str:
        value = self.cleaned_data.get("website", "")
        if value:
            raise forms.ValidationError("No fue posible procesar la solicitud.")
        return ""

    def steps(self):
        """Expone los campos agrupados para un stepper accesible en plantillas."""

        for number, names in self.STEP_FIELDS.items():
            yield number, [self[field_name] for field_name in names]
