import os
import json
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


path = os.path.abspath(__file__)
templates_file = os.getcwd() + '/illusion_templates.json'
with open(templates_file) as f:
    template_file_contents = f.read()
    templates_dict = json.loads(template_file_contents)

app = FastAPI()
app.illusion_templates = templates_dict
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/sdapi/ai/illusion")
async def illusion_diffusion(
        input_image: str = Body("", title='rembg input image'),
        prompt: str = Body("", title='prompt'),
        prompt_strength: float = Body(1.2, title='prompt strength'),
        guidance_scale: float = Body(7.5, title='guidance scale'),
        sampler: str = Body('Euler', title='sampler method'),
        seed: int = Body(-1, title='seed'),
        num_inference_steps: int = Body(30, title='inference steps'),
        resize_to: float = Body(2.0, title='resize image to multiplied by 512, this value can only be of [1, 1.5, 2, 2.5, 3]'),

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
        controlnet_conditioning_scale=prompt_strength if prompt_strength else 1.2,  # illusion strength
        prompt=prompt if prompt else "landscape of a forest, bright sky, vibrant colors",
        negative_prompt='low quality',
        guidance_scale=guidance_scale if guidance_scale else 7.5,
        sampler=sampler if sampler else "Euler",  # Model or sampler "DPM++ Karras SDE"
        control_guidance_start=0,
        control_guidance_end=1.0,
        upscaler_strength=1.0,
        seed=seed if seed else 202134,
        num_inference_steps=num_inference_steps if num_inference_steps else 30,
        resize_to=resize_to if resize_to else 2.0,
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


@app.post("/sdapi/ai/illusion-diffusion")
async def illusion_diffusion(
        input_image: str = Body("", title='rembg input image'),
        template_name: str = Body("", title='prompt'),
):
    if not input_image or not template_name:
        return{
            "success": False,
            "message": "Input image or template_name not found",
            "server_hit_time": '',
            "server_process_time": '',
            "output_image": ''
        }
    utc_time = datetime.now(timezone.utc)
    start_time = time.time()
    print("time now: {0} ".format(strftime("%Y-%m-%d %H:%M:%S", gmtime())))
    input_image = decode_base64_to_image(input_image)
    template = app.illusion_templates[template_name]
    image = inference(
        control_image=input_image,
        controlnet_conditioning_scale=template['prompt_strength'],  # illusion strength
        prompt=template['prompt'],
        negative_prompt=template['negative_prompt'],
        guidance_scale=template['readability_to_creative_scale'],
        sampler=template['sampler'],  # Model or sampler "DPM++ Karras SDE"
        control_guidance_start=0,
        control_guidance_end=1.0,
        upscaler_strength=1.0,
        seed=202134,
        num_inference_steps=template['steps'],
        resize_to=2.0,
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
    uvicorn.run(app, host="0.0.0.0", port=8006)