from typing import Union
import time
from PIL import Image
from io import BytesIO
import base64
import io
import piexif
import piexif.helper
from datetime import datetime, timezone
import logging
import logging.config

from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from time import gmtime, strftime

from app import inference


logger = logging.getLogger(__name__)

app = FastAPI()
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def decode_base64_to_image(img_string):
    img = Image.open(BytesIO(base64.b64decode(img_string)))
    return img


def encode_pil_to_base64(image):
    with io.BytesIO() as output_bytes:
        if image.mode == "RGBA":
            image = image.convert("RGB")
        parameters = image.info.get('parameters', None)
        exif_bytes = piexif.dump({
            "Exif": {piexif.ExifIFD.UserComment: piexif.helper.UserComment.dump(parameters or "",
                                                                                encoding="unicode")}
        })
        image.save(output_bytes, format="JPEG", exif=exif_bytes)
        bytes_data = output_bytes.getvalue()
    return base64.b64encode(bytes_data)


models = [
    "None",
    "u2net",
    "u2netp",
    "u2net_human_seg",
    "u2net_cloth_seg",
    "silueta",
    "isnet-general-use",
    "isnet-anime",
]

@app.post("/sdapi/ai/illusion")
async def rembg_remove(
    input_image: str = Body("", title='rembg input image'),
    prompt: str = Body("", title='prompt'),
):
    if not input_image:
        return{
            "success": False,
            "message": "Input image not found",
            "server_hit_time": '',
            "server_process_time": '',
            "output_image": ''
        }
    utc_time = datetime.now(timezone.utc)
    start_time = time.time()
    print("time now: {0} ".format(strftime("%Y-%m-%d %H:%M:%S", gmtime())))
    input_image = decode_base64_to_image(input_image)
    image = inference(
        control_image=input_image,
        controlnet_conditioning_scale=1.2,  # illusion strength
        prompt=prompt if prompt else "landscape of a forest, bright sky, vibrant colors",
        negative_prompt='low quality',
        guidance_scale=7.5,
        sampler="Euler",  # Model or sampler "DPM++ Karras SDE"
        control_guidance_start=0,
        control_guidance_end=1.0,
        upscaler_strength=1.0,
        seed=-1,

    )

    output_image = encode_pil_to_base64(image[0]).decode("utf-8")

    print("time taken: {0}".format(time.time()-start_time))

    return {
        "success": True,
        "message": "Returned output successfully",
        "server_hit_time": str(utc_time),
        "server_process_time": time.time()-start_time,
        "output_image": output_image
    }

import uvicorn
if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8000)