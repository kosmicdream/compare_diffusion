import argparse
import os

from PIL import Image
from diffusers import StableDiffusionPipeline, StableDiffusionInpaintPipeline
import torch


def terminal_progress_bar(current, total, bar_length=20, task='Image Generation'):
    percent = float(current) * 100 / total
    arrow = '-' * int(percent / 100 * bar_length - 1) + '>'
    spaces = ' ' * (bar_length - len(arrow))

    print('%s Progress: [%s%s] %d %%' % (task, arrow, spaces, percent), end='\r')


def get_all_images_in_subtree(root_dir):
    images = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.png') or file.endswith('.jpg'):
                images.append(os.path.join(root, file))
    return images


def arrange_images(setup, image_paths):
    rows_param_name = setup.get('rows')
    cols_param_name = setup.get('cols')
    subsection_param_name = setup.get('subsections')
    section_param_name = setup.get('sections')

    sections = group_image_paths_into_dict_by_param(image_paths, section_param_name)
    for section_key in sections.keys():
        subsections = group_image_paths_into_dict_by_param(sections[section_key], subsection_param_name)
        for subsection_key in subsections.keys():
            rows = group_image_paths_into_dict_by_param(subsections[subsection_key], rows_param_name)
            for row_key in rows.keys():
                cols = group_image_paths_into_dict_by_param(rows[row_key], cols_param_name)
                for col in cols:
                    # Order cols properly
                    pass
                rows[row_key] = cols
            subsections[subsection_key] = rows
        sections[section_key] = subsections


def group_image_paths_into_dict_by_param(image_paths, param_name):
    image_paths_by_param = {}
    for image_path in image_paths:
        param = image_path.split(param_name + '_')[1].split('/')[0]
        if param not in image_paths_by_param:
            image_paths_by_param[param] = []
        image_paths_by_param[param].append(image_path)
    return image_paths_by_param


def complete_sentences(strings):
    # Initialize an empty list to store the completed sentences
    sentences = []

    # Initialize an empty string to store the current sentence
    current_sentence = ""

    # Iterate through the strings
    for string in strings:
        # Add the string to the current sentence
        current_sentence += string + " "

        # If the current string ends with a quotation mark, it is the end of a sentence
        if string[-1] == "'":
            # Add the completed sentence to the list of sentences and reset the current sentence
            sentences.append(current_sentence)
            current_sentence = ""

        # Return the list of sentences
    return sentences


def get_image_paths(dir):
    image_paths = []
    for root, dirs, files in os.walk(dir):
        for file in files:
            if file.endswith('.png') or file.endswith('.jpg'):
                image_paths.append(os.path.join(root, file))
    return image_paths


def validate(fp: str) -> bool:
    try:
        Image.open(fp)
    except:
        print(f'WARNING: Image cannot be opened: {fp}')
        return False


def extract_input_num(self, path):
    return int(path.split('/')[-1].split('.')[0][1:])


def clean(image_files, mask_files):
    print('ImageStore: Sorting images and masks')

    clean_images = []
    clean_masks = []

    # Create a dictionary that maps image numbers to filenames
    image_dict = {}
    for img in image_files:
        # If image is valid
        if validate(img):
            # Extract the number from the filename
            img_num = extract_input_num(img)
            image_dict[img_num] = img

    # Create a dictionary that maps mask numbers to filenames
    mask_dict = {}
    for msk in mask_files:
        # If mask is valid
        if validate(msk):
            # Extract the number from the filename
            msk_num = extract_input_num(msk)
            mask_dict[msk_num] = msk

    # Iterate over the keys (numbers) in the image dictionary
    for img_num in image_dict:
        # Check if the number exists in the mask dictionary
        if img_num in mask_dict:
            # If it does, add the corresponding filenames to the clean lists
            clean_images.append(image_dict[img_num])
            clean_masks.append(mask_dict[img_num])

    return clean_images, clean_masks


parser = argparse.ArgumentParser(description='Stable Diffusion Output Comparison')
parser.add_argument('--type', type=str, required=True, choices=['img2img', 'txt2img', 'inpaint'])
parser.add_argument('--rows', type=str, required=True)
parser.add_argument('--cols', type=str, required=True)
parser.add_argument('--subsections', type=str, default=None)
parser.add_argument('--sections', type=str, default=None)
parser.add_argument('--models', type=str, nargs='+', required=True)
parser.add_argument('--cfg_scale_list', type=float, nargs='+', required=True)
parser.add_argument('--denoising_strength_list', type=float, nargs='+', required=True)
parser.add_argument('--prompts', type=str, nargs='+', required=True)
parser.add_argument('--negative_prompts', type=str, nargs='*')
parser.add_argument('--seeds', type=int, nargs='*', default=1)

if __name__ == "__main__":
    args = parser.parse_args()

    type = args.type
    if type == 'img2img':
        images, masks = [image_path for image_path in get_image_paths('input/images') if validate(image_path)], None
    elif type == 'inpaint':
        images, masks = clean(get_image_paths('input/images'), get_image_paths('input/masks'))
    else:
        images, masks = None, None

    model_paths = args.models
    cfg_scale_list = args.cfg_scale_list
    denoising_strength_list = args.denoising_strength_list
    prompts = complete_sentences(args.prompts)
    if args.negative_prompts:
        negative_prompts = complete_sentences(args.negative_prompts)
    else:
        negative_prompts = ['']
    seeds = args.seeds

    output_counter = 0
    num_images_to_generate = len(images) * len(model_paths) * len(cfg_scale_list) * len(denoising_strength_list) * \
                             len(prompts) * len(negative_prompts) * len(seeds)

    for model_path in model_paths:
        folder = os.path.join('output', os.path.basename(model_path))
        if type == 'inpaint':
            model = StableDiffusionInpaintPipeline.from_pretrained(model_path, torch_dtype=torch.float16,
                                                                   revision="fp16")
        else:
            model = StableDiffusionPipeline.from_pretrained(model_path, torch_dtype=torch.float16, revision="fp16")
        model = model.to("cuda")
        for prompt in prompts:
            folder = os.path.join(folder, 'pmt_' + prompt.lower().replace(' ', '_'))
            for negative_prompt in negative_prompts:
                folder = os.path.join(folder, 'neg_pmt_' + negative_prompt.lower().replace(' ', '_'))
                for cfg_scale in cfg_scale_list:
                    folder = os.path.join(folder, 'cfg_' + str(cfg_scale))
                    for denoising_strength in denoising_strength_list:
                        folder = os.path.join(folder, 'dns_' + str(denoising_strength))
                        for seed in seeds:
                            folder = os.path.join(folder, 'seed_' + str(seed))
                            try:
                                if type == 'txt2img':
                                    # Call txt2img
                                    output = model(prompt, negative_prompt, cfg_scale, denoising_strength).images[0]
                                    # Generate image name as increment of previous image
                                    output.save(folder + 'output_' + str(output_counter) + '.png')
                                    output_counter += 1
                                    terminal_progress_bar(output_counter, num_images_to_generate)
                            except:
                                print('Error generating image with params: ' + str(prompt) + ' ' + str(negative_prompt)
                                      + ' ' + str(cfg_scale) + ' ' + str(denoising_strength))
                            for idx, image in enumerate(images):
                                try:
                                    if type == 'inpaint':
                                        # Call inpaint
                                        mask = masks[idx]
                                        output = model(prompt=prompt, image=image, mask_image=mask).images[0]
                                        output.save(folder + image)
                                        output_counter += 1
                                        terminal_progress_bar(output_counter, num_images_to_generate)
                                    elif type == 'img2img':
                                        # Call img2img
                                        output = \
                                        model(image, prompt, negative_prompt, cfg_scale, denoising_strength).images[0]
                                        output.save(folder + image)
                                        output_counter += 1
                                        terminal_progress_bar(output_counter, num_images_to_generate)
                                except:
                                    print('Error generating image with params: ' + str(prompt) + ' ' + str(
                                        negative_prompt)
                                          + ' ' + str(cfg_scale) + ' ' + str(denoising_strength))
    #
    # print('Generated ' + str(output_counter) + ' images.')
    #
    # image_paths = get_all_images_in_subtree('results')

    # Make report first page

    # Make section title

    # Make subsection title

    # Make col header

    # Generate rows

    # Concat rows with section title, subsection title, and col header
