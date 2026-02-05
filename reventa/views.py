from django.contrib.auth.decorators import login_required
from django.shortcuts import render

@login_required
def inicio_reventa(request):
    return render(request, "reventa/inicio_reventa.html")
