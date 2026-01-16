from django.contrib import admin
from django.urls import path, include
from inicio import views as inicio_views
from django.contrib.auth import views as auth_views

# ✅ AGREGADOS PARA MEDIA (NO ROMPEN NADA)
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
    path('', inicio_views.ingreso, name='ingreso'),

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

    # 🔴 CAMBIO CLAVE (SOLO ESTE)
    path(
        'clientes/',
        include(('clientes.urls', 'clientes'), namespace='clientes')
    ),

    path('cuentas/', include('cuentas.urls')),
    path('calendario/', include('calendario.urls')),

    # ===============================
    # ⭐ NUEVAS ÁREAS DEL SISTEMA
    # ===============================

    # 👉 Ventas
    path('ventas/', include('ventas.urls')),

    # 👉 Gestoría
    path('gestoria/', include('gestoria.urls')),

    # 👉 Facturación
    path('facturacion/', include('facturacion.urls')),

    # 👉 Reportes
    path('reportes/', include('reportes.urls')),

    # 👉 Asistencia
    path('asistencia/', include('asistencia.urls')),

    # ===============================
    # 📄 BOLETOS DE COMPRAVENTA
    # ===============================
    path('boletos/', include('boletos.urls')),

    # ===============================
    # 💸 DEUDAS (NUEVO)
    # ===============================
    path('deudas/', include('deudas.urls')),
]

# ==========================================================
# 📂 MEDIA FILES (SOLO EN DESARROLLO)
# ==========================================================
if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
