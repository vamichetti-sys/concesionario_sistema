from django.conf import settings


def usuario_principal(request):
    """
    Expone settings.USUARIO_PRINCIPAL a todos los templates como
    variable USUARIO_PRINCIPAL, para condicionar la visibilidad del
    menú "Proyectos" en el sidebar.
    """
    return {
        'USUARIO_PRINCIPAL': getattr(settings, 'USUARIO_PRINCIPAL', ''),
    }
