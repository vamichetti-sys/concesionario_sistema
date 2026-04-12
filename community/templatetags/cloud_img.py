from django import template

register = template.Library()


@register.filter
def cloud_opt(url, size="800"):
    """
    Transforma una URL de Cloudinary para servir una versión optimizada.
    Uso: {{ foto.imagen.url|cloud_opt:"600" }}
    Agrega w_{size},q_auto,f_auto a la URL de Cloudinary.
    Si no es Cloudinary, devuelve la URL sin cambios.
    """
    url = str(url)
    if "res.cloudinary.com" not in url:
        return url

    # URL de Cloudinary: .../upload/v123456/path/imagen.jpg
    # Insertar transformaciones después de /upload/
    parts = url.split("/upload/")
    if len(parts) == 2:
        return f"{parts[0]}/upload/w_{size},q_auto,f_auto/{parts[1]}"
    return url


@register.filter
def cloud_thumb(url):
    """Versión miniatura (150px) para strips."""
    return cloud_opt(url, "150")
