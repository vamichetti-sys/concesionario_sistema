import io
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from vehiculos.models import Vehiculo
from community.models import FotoVehiculo

MEDIA_TMP = tempfile.mkdtemp()


def _jpg():
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), "red").save(buf, "JPEG")
    return SimpleUploadedFile("f.jpg", buf.getvalue(), content_type="image/jpeg")


@override_settings(
    SECURE_SSL_REDIRECT=False,
    MEDIA_ROOT=MEDIA_TMP,
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    },
)
class CatalogoDescargaFotosTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_TMP, ignore_errors=True)

    def _vehiculo(self, estado):
        v = Vehiculo.objects.create(
            marca="Ford", modelo="Focus", dominio="AB123CD", anio=2020,
            precio=1000, estado=estado)
        FotoVehiculo.objects.create(vehiculo=v, imagen=_jpg(), es_portada=True)
        FotoVehiculo.objects.create(vehiculo=v, imagen=_jpg())
        return v

    def test_catalogo_muestra_botones_de_descarga(self):
        v = self._vehiculo("stock")
        r = self.client.get(reverse("community:catalogo_publico"))
        self.assertContains(r, f"descargarFotos(0")
        self.assertContains(r, "lightbox-download")
