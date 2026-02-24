from django.contrib import admin
from django.urls import path, include
from inicio import views as inicio_views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # ===============================
    # 🛠 ADMIN
    # ===============================
    path('admin/', admin.site.urls),

    # ===============================
    # 🔐 LOGIN PRINCIPAL
    # ===============================
    path('login/', inicio_views.ingreso, name='ingreso'),
    path('', inicio_views.ingreso),

    # ===============================
    # 🏠 DASHBOARD PRINCIPAL
    # ===============================
    path('inicio/', inicio_views.inicio, name='inicio'),

    # ===============================
    # 🚪 CERRAR SESIÓN
    # ===============================
    path('logout/', inicio_views.cerrar_sesion, name='logout'),

    # ===============================
    # 🔁 RECUPERAR CONTRASEÑA
    # ===============================
    path(
        'recuperar/',
        auth_views.PasswordResetView.as_view(
            template_name='inicio/recuperar.html'
        ),
        name='password_reset'
    ),
    path(
        'recuperar/enviado/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='inicio/recuperar_enviado.html'
        ),
        name='password_reset_done'
    ),
    path(
        'recuperar/<uidb64>/<token>/',
        auth_views.PasswordResetConfirmView.as_view(
            template_name='inicio/restablecer.html'
        ),
        name='password_reset_confirm'
    ),
    path(
        'recuperar/completo/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='inicio/restablecer_completo.html'
        ),
        name='password_reset_complete'
    ),

    # ===============================
    # 📦 APPS INTERNAS
    # ===============================
    path('vehiculos/', include('vehiculos.urls')),
    path(
        'clientes/',
        include(('clientes.urls', 'clientes'), namespace='clientes')
    ),
    path('cuentas/', include('cuentas.urls')),
    path('calendario/', include('calendario.urls')),

    # ===============================
    # ⭐ NUEVAS ÁREAS DEL SISTEMA
    # ===============================
    path('compraventa/', include('compraventa.urls')),
    path('ventas/', include('ventas.urls')),
    path('gestoria/', include('gestoria.urls')),
    path('facturacion/', include('facturacion.urls')),
    path('reportes/', include('reportes.urls')),
    path('asistencia/', include('asistencia.urls')),
    path('documentacion/', include('documentacion.urls')),

    # ===============================
    # 📄 BOLETOS DE COMPRAVENTA
    # ===============================
    path('boletos/', include('boletos.urls')),

    # ===============================
    # 💸 DEUDAS
    # ===============================
    path('deudas/', include('deudas.urls')),

    # ===============================
    # 📋 PRESUPUESTOS (NUEVO)
    # ===============================
    path('presupuestos/', include('presupuestos.urls')),
]

# ==========================================================
# 📂 MEDIA FILES (SOLO EN DESARROLLO)
# ==========================================================
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )