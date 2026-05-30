from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def index(request):
    """Placeholder del módulo Financiación (Gestión Personal).
    Por ahora solo muestra un mensaje 'en construcción'.
    """
    return render(request, "financiacion/index.html", {
        "page_title": "Financiación",
    })
