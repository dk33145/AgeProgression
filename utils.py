import consts
import os

from shutil import copyfile
import numpy as np
from collections import namedtuple

import torch
import torchvision.transforms as transforms
from torchvision.datasets import ImageFolder

def merge(images, size):
    h, w = images.shape[2], images.shape[3]
    img = np.zeros((3, h * size[0], w * size[1]))

    for idx, image in enumerate(images):
        i = idx % size[1]
        j = int(idx / size[1])
        img[0][j * h:j * h + h, i * w:i * w + w] = image[0]
        img[1][j * h:j * h + h, i * w:i * w + w] = image[1]
        img[2][j * h:j * h + h, i * w:i * w + w] = image[2]

    return img

def get_utkface_dataset(root):
    ret = lambda: ImageFolder(os.path.join(root, 'labeled'), transform=transforms.Compose([
        transforms.Resize(size=(128, 128)),
        transforms.ToTensor(),
        transforms.Lambda(lambda x: 2 * x - 1)  # [0:1] -> [-1:1]
    ]))
    try:
        return ret()
    except (RuntimeError, FileNotFoundError):
        sort_to_classes(os.path.join(root, 'unlabeled'), print_cycle=1000)
        return ret()

def sort_to_classes(root, print_cycle=np.inf):
    # Example UTKFace cropped and aligned image file format: [age]_[gender]_[race]_[date&time].jpg.chip.jpg
    # Should be 23613 images, use print_cycle >= 1000
    # Make sure you have > 100 MB free space

    def log(text):
        print('[UTKFace dset labeler] ' + text)

    log('Starting labeling process...')
    files = [f for f in os.listdir(root) if os.path.isfile(os.path.join(root, f))]
    if not files:
        raise FileNotFoundError('No image files in '+root)
    copied_count = 0
    sorted_folder = os.path.join(root, '..', 'labeled')
    if not os.path.isdir(sorted_folder):
        os.mkdir(sorted_folder)

    for f in files:
        matcher = consts.UTKFACE_ORIGINAL_IMAGE_FORMAT.match(f)
        if matcher is None:
            continue
        age, gender, dtime = matcher.groups()
        srcfile = os.path.join(root, f)
        label = Label(int(age), int(gender))
        dstfolder = os.path.join(sorted_folder, label.to_str())
        dstfile = os.path.join(dstfolder, dtime+'.jpg')
        if os.path.isfile(dstfile):
            continue
        if not os.path.isdir(dstfolder):
            os.mkdir(dstfolder)
        copyfile(srcfile, dstfile)
        copied_count += 1
        if copied_count % print_cycle == 0:
            log('Copied %d files.' % copied_count)
    log('Finished labeling process.')


def str_to_tensor(text):
    age_group, gender = text.split('.')
    age_tensor = -torch.ones(consts.NUM_AGES)
    age_tensor[int(age_group)] *= -1
    gender_tensor = -torch.ones(consts.NUM_GENDERS)
    gender_tensor[int(gender)] *= -1
    result = torch.cat((age_tensor, gender_tensor), 0)
    result = result.to(device=consts.device)
    return result


class Label(namedtuple('Label', ('age', 'gender'))):
    def __init__(self, age, gender):
        super(Label, self).__init__()
        _age = self.age - 1
        if _age < 20:
            self.age_group = max(_age // 5, 0)  # first 4 age groups are for kids <= 20, 5 years intervals
        else:
            self.age_group = min(4 + (_age - 20) // 10, consts.NUM_AGES - 1)  # last (6?) age groups are for adults > 20, 10 years intervals

    def to_str(self):
        return '%d.%d' % (self.age_group, self.gender)

    def to_tensor(self):
        return str_to_tensor(self.to_str())


def two_sided(x):
    return 2 * (x - 0.5)


def one_sided(x):
    return (x + 1) / 2
