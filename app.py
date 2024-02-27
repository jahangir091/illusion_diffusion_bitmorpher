import torch
import os
import gradio as gr
from PIL import Image
import random
from diffusers import (
    DiffusionPipeline,
    AutoencoderKL,
    StableDiffusionControlNetPipeline,
    ControlNetModel,
    StableDiffusionLatentUpscalePipeline,
    StableDiffusionImg2ImgPipeline,
    StableDiffusionControlNetImg2ImgPipeline,
    DPMSolverMultistepScheduler,  # <-- Added import
    EulerDiscreteScheduler  # <-- Added import
)

from illusion_style import css

BASE_MODEL = "SG161222/Realistic_Vision_V5.1_noVAE"

# Initialize both pipelines
vae = AutoencoderKL.from_pretrained("stabilityai/sd-vae-ft-mse", torch_dtype=torch.float16)
#init_pipe = DiffusionPipeline.from_pretrained("SG161222/Realistic_Vision_V5.1_noVAE", torch_dtype=torch.float16)
controlnet = ControlNetModel.from_pretrained("monster-labs/control_v1p_sd15_qrcode_monster", torch_dtype=torch.float16)#, torch_dtype=torch.float16)
main_pipe = StableDiffusionControlNetPipeline.from_pretrained(
    BASE_MODEL,
    controlnet=controlnet,
    vae=vae,
    safety_checker=None,
    torch_dtype=torch.float16,
).to("cuda")
#main_pipe.unet = torch.compile(main_pipe.unet, mode="reduce-overhead", fullgraph=True)
#main_pipe.unet.to(memory_format=torch.channels_last)
#main_pipe.unet = torch.compile(main_pipe.unet, mode="reduce-overhead", fullgraph=True)
#model_id = "stabilityai/sd-x2-latent-upscaler"
image_pipe = StableDiffusionControlNetImg2ImgPipeline.from_pretrained(BASE_MODEL, unet=main_pipe.unet, vae=vae, controlnet=controlnet, safety_checker=None, torch_dtype=torch.float16).to("cuda")
#image_pipe.unet = torch.compile(image_pipe.unet, mode="reduce-overhead", fullgraph=True)
#upscaler = StableDiffusionLatentUpscalePipeline.from_pretrained(model_id, torch_dtype=torch.float16)
#upscaler.to("cuda")


# Sampler map
SAMPLER_MAP = {
    "DPM++ Karras SDE": lambda config: DPMSolverMultistepScheduler.from_config(config, use_karras=True, algorithm_type="sde-dpmsolver++"),
    "Euler": lambda config: EulerDiscreteScheduler.from_config(config),
}

def center_crop_resize(img, output_size=(512, 512)):
    width, height = img.size

    # Calculate dimensions to crop to the center
    new_dimension = min(width, height)
    left = (width - new_dimension)/2
    top = (height - new_dimension)/2
    right = (width + new_dimension)/2
    bottom = (height + new_dimension)/2

    # Crop and resize
    img = img.crop((left, top, right, bottom))
    img = img.resize(output_size)

    return img

def resize_with_ratio(img, resize_to=1):
    width, height = img.size
    if resize_to > 1:
        return img.resize((width*resize_to, height*resize_to))
    # base_size = 512
    # if width > height:
    #     w_percent = (base_size / float(img.size[0]))
    #     new_height = int((float(img.size[1]) * float(w_percent)))
    #     img = img.resize((base_size, new_height))
    # else:
    #     h_percent = (base_size / float(img.size[1]))
    #     new_width = int((float(img.size[0]) * float(h_percent)))
    #     img = img.resize((new_width, base_size))
    return img

def common_upscale(samples, width, height, upscale_method, crop=False):
        if crop == "center":
            old_width = samples.shape[3]
            old_height = samples.shape[2]
            old_aspect = old_width / old_height
            new_aspect = width / height
            x = 0
            y = 0
            if old_aspect > new_aspect:
                x = round((old_width - old_width * (new_aspect / old_aspect)) / 2)
            elif old_aspect < new_aspect:
                y = round((old_height - old_height * (old_aspect / new_aspect)) / 2)
            s = samples[:,:,y:old_height-y,x:old_width-x]
        else:
            s = samples

        return torch.nn.functional.interpolate(s, size=(height, width), mode=upscale_method)

def upscale(samples, upscale_method, scale_by):
        #s = samples.copy()
        width = round(samples["images"].shape[3] * scale_by)
        height = round(samples["images"].shape[2] * scale_by)
        s = common_upscale(samples["images"], width, height, upscale_method, "disabled")
        return (s)

# Inference function
def inference(
    control_image: Image.Image,
    prompt: str,
    negative_prompt: str,
    guidance_scale: float = 8.0,
    controlnet_conditioning_scale: float = 1,
    control_guidance_start: float = 1,    
    control_guidance_end: float = 1,
    upscaler_strength: float = 0.5,
    seed: int = -1,
    sampler = "DPM++ Karras SDE",
    num_inference_steps: int = 30,
    resize_to: float = 2.0,
    progress = gr.Progress(track_tqdm=True)
):
    if prompt is None or prompt == "":
        raise gr.Error("Prompt is required")
    
    # Generate the initial image
    #init_image = init_pipe(prompt).images[0]

    # Rest of your existing code
    control_image_small = center_crop_resize(control_image)
    main_pipe.scheduler = SAMPLER_MAP[sampler](main_pipe.scheduler.config)
    my_seed = random.randint(0, 2**32 - 1) if seed == -1 else seed
    generator = torch.manual_seed(my_seed)
    
    out = main_pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        image=control_image_small,
        guidance_scale=float(guidance_scale),
        controlnet_conditioning_scale=float(controlnet_conditioning_scale),
        generator=generator,
        control_guidance_start=float(control_guidance_start),
        control_guidance_end=float(control_guidance_end),
        num_inference_steps=30,
        output_type="latent"
    )
    control_image_large = center_crop_resize(control_image, (int(512*resize_to), int(512*resize_to)))
    upscaled_latents = upscale(out, "nearest-exact", resize_to)
    out_image = image_pipe(
        prompt=prompt,
        negative_prompt=negative_prompt,
        control_image=control_image_large,        
        image=upscaled_latents,
        guidance_scale=float(guidance_scale),
        generator=generator,
        num_inference_steps=num_inference_steps,
        strength=upscaler_strength,
        control_guidance_start=float(control_guidance_start),
        control_guidance_end=float(control_guidance_end),
        controlnet_conditioning_scale=float(controlnet_conditioning_scale)
    )
    return out_image["images"][0], gr.update(visible=True), my_seed
        
    #return out

with gr.Blocks(css=css) as app:
    gr.Markdown(
        '''
        <center> 
        <span font-size:16px;"></span>  
        </center>
        '''
    )
    
    with gr.Row():
        with gr.Column():
            control_image = gr.Image(label="Upload QR code", type="pil", elem_id="control_image")
            controlnet_conditioning_scale = gr.Slider(minimum=0.0, maximum=2.0, step=0.01, value=1.2, label="Prompt strength", elem_id="illusion_strength")
            num_inference_steps = gr.Slider(minimum=0, maximum=100, step=1, value=30, label="number of inference steps", elem_id="num_inference_steps")
            resize_to = gr.Slider(minimum=1, maximum=2, step=0.5, value=2, label="resize image to", elem_id="resize_image")

            prompt = gr.Textbox(label="Prompt", elem_id="prompt")
            negative_prompt = gr.Textbox(label="Negative Prompt", value="low quality", elem_id="negative_prompt")
            with gr.Accordion(label="Advanced Options", open=False):
                guidance_scale = gr.Slider(minimum=0.0, maximum=50.0, step=0.25, value=6, label="Readabilty to Creative Scale")
                sampler = gr.Dropdown(choices=list(SAMPLER_MAP.keys()), value="Euler")
                control_start = gr.Slider(minimum=0.0, maximum=1.0, step=0.1, value=0, visible=False, label="Start of ControlNet")
                control_end = gr.Slider(minimum=0.0, maximum=1.0, step=0.1, value=1, visible=False, label="End of ControlNet")
                strength = gr.Slider(minimum=0.0, maximum=1.0, step=0.1, value=1, visible=False, label="Strength of the upscaler")
                seed = gr.Slider(minimum=-1, maximum=9999999999, step=1, value=-1, label="Seed", info="-1 means random seed")
                used_seed = gr.Number(label="Last seed used",visible=False,interactive=False) 
            run_btn = gr.Button("Run")
        with gr.Column():
            result_image = gr.Image(label="QR Code", interactive=False,show_share_button=False, elem_id="output")


    prompt.submit(
        inference,
        inputs=[control_image, prompt, negative_prompt, guidance_scale, controlnet_conditioning_scale, control_start, control_end, strength, seed, sampler, num_inference_steps, resize_to],
        outputs=[result_image, seed]
    )
    run_btn.click(
        inference,
        inputs=[control_image, prompt, negative_prompt, guidance_scale, controlnet_conditioning_scale, control_start, control_end, strength, seed, sampler, num_inference_steps, resize_to],
        outputs=[result_image, seed]
    )
  
app.queue(max_size=21)

if __name__ == "__main__":
    app.launch(share=False, server_name='0.0.0.0', server_port=8006)