import os
import json
import time
import requests
from PIL import Image
from io import BytesIO
import base64
import io
import uuid
import piexif
import piexif.helper
from datetime import datetime, timezone
import logging
import logging.config
import uvicorn
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from time import gmtime, strftime

from app import inference

logger = logging.getLogger(__name__)


def get_img_path(directory_name):
    current_dir = '/tmp'
    img_directory = current_dir + '/.temp' + directory_name
    os.makedirs(img_directory, exist_ok=True)
    img_file_name = uuid.uuid4().hex[:20] + '.jpg'
    return img_directory + img_file_name


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


illusion_templates_res = requests.get('https://photolab-ai.com/media/giff/illusion_templates/illusion_templates.json')
templates_dict = illusion_templates_res.json()

app = FastAPI(docs_url="/docs")
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
        input_image: str = Body("", title='input image'),
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


@app.get("/ai/api/v1/illusion-server-test")
def illusion_server_test():
    return {"Illusion diffusion server is working fine. OK!"}


@app.post("/ai/api/v1/illusion-diffusion")
async def illusion_diffusion(
        image: str = Body("", title='illusion input image'),
        template_name: str = Body("", title='illusion template name'),
        prompt: str = Body("", title='user prompt'),
        seed: bool = Body(False, title='seed, if True then seed will be -1'),
):
    if not image:
        return{
            "success": False,
            "message": "Input image not found",
            "server_process_time": '',
            "output_image_url": ''
        }
    if not template_name and not prompt:
        return {
            "success": False,
            "message": "Please provide template name or prompt",
            "server_process_time": '',
            "output_image_url": ''
        }
    utc_time = datetime.now(timezone.utc)
    start_time = time.time()
    print("time now: {0} ".format(strftime("%Y-%m-%d %H:%M:%S", gmtime())))
    input_image = decode_base64_to_image(image)
    if template_name:
        template = app.illusion_templates[template_name]
    else:
        template = app.illusion_templates['planet']
        template['prompt'] = prompt
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
        seed=-1 if seed else 202134,
        num_inference_steps=template['steps'],
        resize_to=2.0,
    )

    # output_image = encode_pil_to_base64(image[0]).decode("utf-8")
    out_images_directory_name = '/illusion_diffusion_images/'
    out_image_path = get_img_path(out_images_directory_name)
    image[0].save(out_image_path)

    print("server process time: {0}".format(time.time()-start_time))

    return {
        "success": True,
        "message": "Returned output successfully",
        "server_process_time": time.time()-start_time,
        "output_image_url": 'media' + out_images_directory_name + out_image_path.split('/')[-1]
    }


if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8005)