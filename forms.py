from django import forms
from csdjango.sb import models

class PaySlipForm(forms.Form):
    employee = forms.ModelChoiceField(models.Account.objects.filter(parent__name="Creditors"))
    date = forms.DateField()
    gross = forms.DecimalField(decimal_places=2)
    paye = forms.DecimalField(decimal_places=2)
    uif = forms.DecimalField(decimal_places=2, required=False)
    bonus = forms.DecimalField(decimal_places=2, required=False)

class SourceDocForm(forms.ModelForm):
    class Meta:
        model = models.SourceDoc
