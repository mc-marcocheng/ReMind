import os
import tempfile
from pathlib import Path

import pyimgur
import tenacity
from PIL.Image import Image


def upload_image(image) -> str:
    """
    Upload an image and return the link.
    """

    if isinstance(image, Image):
        tmp_dir = tempfile.TemporaryDirectory()
        image_path = (Path(tmp_dir.name) / "tmp.png").as_posix()
        image.save(image_path)
    else:
        image_path = image

    image_link = None
    if os.environ.get("IMGUR_CLIENT_ID") and os.environ.get("IMGUR_CLIENT_SECRET"):
        image_link = upload_image_to_imgur(image_path)
    image_link = image_link or image_path

    if isinstance(image, Image):
        tmp_dir.cleanup()
    return image_link


@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(min=5, max=30),
    reraise=True,
)
def upload_image_to_imgur(image_path: str) -> str:
    """
    Upload an image to Imgur and return the link.
    """
    client = pyimgur.Imgur(client_id=os.environ.get("IMGUR_CLIENT_ID"), client_secret=os.environ.get("IMGUR_CLIENT_SECRET"))
    image = client.upload_image(image_path)
    return image.link
