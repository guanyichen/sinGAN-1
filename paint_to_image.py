import os
import cv2
import torch
import numpy as np
import matplotlib.pyplot as plt
from torch import nn

from chanye._utils_torch import reshape_batch_torch
from chanye._visualizer import preprocess
from sinGAN import SinGAN
from utils import normalize_image


class Paint2Image(SinGAN):
    def __init__(self, config):
        super().__init__(config)

        naive_img = plt.imread(os.path.join(config['path_dataset_root'], config['path_naive']))
        self.naive_img = normalize_image(naive_img)

        self.naive_height_pyramid, self.naive_width_pyramid, self.naive_pyramid = [], [], []
        width, height, _ = self.naive_img.shape
        for scale in range(self.num_scale + 1):
            multiplier = self.multiplier_pyramid[scale]
            height_scaled = int(round(height * multiplier))
            width_scaled = int(round(width * multiplier))

            self.naive_height_pyramid.append(height_scaled)
            self.naive_width_pyramid.append(width_scaled)

            processed = cv2.resize(self.naive_img, (height_scaled, width_scaled))
            processed = torch.tensor(np.transpose(processed, [2, 0, 1])[np.newaxis])
            self.naive_pyramid.append(processed.to(self.device, torch.float))

    def generate_paint2image(self, init_scale):
        if init_scale == -1:
            init_scale = self.num_scale

        self.paint2image_pyramid = []  # just for enjoy
        for scale in range(init_scale, self.num_scale + 1):
            generator = self.generator_pyramid[scale]
            noise_optimal = self.noise_optimal_pyramid[scale]
            sigma = self.sigma_pyramid[scale]

            if scale == init_scale:
                naive = self.naive_pyramid[init_scale]
                paint2image = generator(naive, noise_optimal * sigma)

            else:
                paint2image = nn.Upsample(
                    (self.naive_width_pyramid[scale], self.naive_height_pyramid[scale])
                )(paint2image)
                paint2image = generator(paint2image, noise_optimal * sigma)

            self.paint2image_pyramid.append(paint2image)
        return paint2image

    def test_samples(self, save):
        os.makedirs(self.path_sample, exist_ok=True)

        self.eval_mode_all()
        with torch.no_grad():
            if not self.num_scale % 2:
                n_rows = 2
                n_cols = self.num_scale // 2

                save_image, _, _ = reshape_batch_torch(
                    torch.cat(
                        [self.generate_paint2image(scale).clamp(-1, 1) for scale in range(1, self.num_scale + 1)]),
                    padding=2, n_rows=n_rows, n_cols=n_cols
                )
            else:
                paint2images = [self.generate_paint2image(scale).clamp(-1, 1) for scale in range(1, self.num_scale + 1)]
                paint2images += [torch.zeros_like(paint2images[0])]
                save_image, _, _ = reshape_batch_torch(
                    torch.cat(paint2images), n_rows=2, n_cols=-1
                )

            save_image = preprocess(save_image)  # preprocess image
            if save:
                save_name = os.path.join(self.path_sample, "paint2image.jpg")
                plt.imsave(save_name, save_image)
                print("Paint to Image samples Saved:" + save_name)
        return save_image
