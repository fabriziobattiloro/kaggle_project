import os
import random

import torch
from torch import optim
from torch.autograd import Variable
import torch.nn.functional as F
from torch.nn import NLLLoss2d
from torch.optim.lr_scheduler import StepLR
from torchvision.utils import save_image
import torchvision.transforms as standard_transforms
import torchvision.utils as vutils
from tensorboardX import SummaryWriter

from models.model_BiSeNet2 import BiSeNet
from models.config import cfg, __C
from models.loading_data import loading_data
from models.utils import *
from models.timer import Timer
from models.loss import CB_loss
import pdb

exp_name = cfg.TRAIN.EXP_NAME
log_txt = cfg.TRAIN.EXP_LOG_PATH + '/' + exp_name + '.txt'
writer = SummaryWriter(cfg.TRAIN.EXP_PATH+ '/' + exp_name)

pil_to_tensor = standard_transforms.ToTensor()
train_loader, val_loader, restore_transform = loading_data()

def main():

    cfg_file = open('/kaggle/working/project-code1/multiclass/models/config.py',"r")  
    cfg_lines = cfg_file.readlines()
    
    with open(log_txt, 'a') as f:
            f.write(''.join(cfg_lines) + '\n\n\n\n')
    if len(cfg.TRAIN.GPU_ID)==1:
        torch.cuda.set_device(cfg.TRAIN.GPU_ID[0])
    torch.backends.cudnn.benchmark = True

    net = []  
    net = BiSeNet(cfg.DATA.NUM_CLASSES) 

    if len(cfg.TRAIN.GPU_ID)>1:
        net = torch.nn.DataParallel(net, device_ids=cfg.TRAIN.GPU_ID).cuda()
    else:
        net=net.cuda()

    net.train()
    class_counts = [0] * cfg.DATA.NUM_CLASSES
    criterion = CB_loss()
    criterion.cuda()

   
    optimizer = optim.Adam(net.parameters(), lr=cfg.TRAIN.LR, weight_decay=cfg.TRAIN.WEIGHT_DECAY)
    scheduler = StepLR(optimizer, step_size=cfg.TRAIN.NUM_EPOCH_LR_DECAY, gamma=cfg.TRAIN.LR_DECAY)
    _t = {'train time' : Timer(),'val time' : Timer()} 
    validate(val_loader, net, criterion, optimizer, -1, restore_transform, class_counts)
    for epoch in range(cfg.TRAIN.MAX_EPOCH):
        _t['train time'].tic()
        train(train_loader, net, criterion, optimizer, epoch, class_counts)
        _t['train time'].toc(average=False)
        print('training time of one epoch: {:.2f}s'.format(_t['train time'].diff))
        _t['val time'].tic()
        validate(val_loader, net, criterion, optimizer, epoch, restore_transform, class_counts)
        _t['val time'].toc(average=False)
        print('val time of one epoch: {:.2f}s'.format(_t['val time'].diff))


def train(train_loader, net, criterion, optimizer, epoch, class_counts):
    for i, data in enumerate(train_loader, 0):
        inputs, labels = data
        inputs = Variable(inputs).cuda()
        labels = Variable(labels).cuda()

        outputs = net(inputs)
        out1, out2, out3= outputs
        # Resize the labels tensor to match the output tensor dimensions

        loss1 = criterion(out1, labels, class_counts)
        loss2 = criterion(out2, labels, class_counts)
        loss3 = criterion(out3, labels, class_counts)

        losses = loss1 + loss2 + loss3
        optimizer.zero_grad()
        losses.backward()
        optimizer.step()



def validate(val_loader, net, criterion, optimizer, epoch, restore, class_counts):
    net.eval()
    criterion.cpu()
    input_batches = []
    output_batches = []
    label_batches = []
    mean_classes = []
    iou_ = 0.0
    mean_classe0 = 0
    mean_classe1 = 0
    mean_classe2 = 0
    mean_classe3 = 0
    mean_classe4 = 0
    mean_tot = 0
    for i in range(len(class_counts)):
        class_counts[i] = 0

    
    for vi, data in enumerate(val_loader, 0):
        inputs, labels = data
        inputs = Variable(inputs, volatile=True).cuda()
        labels = Variable(labels, volatile=True).cuda()
        outputs = net(inputs)
        out1, out2, out3 = outputs

        out1 = F.softmax(out1, dim=1)  # Apply softmax activation function along the channel dimension
        
        # For each pixel, determine the class with highest probability
        max_value, predicted = torch.max(out1.data, 1)  
        
        # Calculate the pixel counts for each class
        for c in range(cfg.DATA.NUM_CLASSES):
            class_mask = predicted == c
            class_counts[c] += torch.sum(class_mask).item()
            #print(f"pixels {c}: {class_counts[c]} pixels")
       

        mean0, mean1, mean2, mean3, mean4, mean5 = calculate_mean_iu([predicted.unsqueeze_(1).data.cpu().numpy()], 
                                        [labels.unsqueeze_(1).data.cpu().numpy()], cfg.DATA.NUM_CLASSES)
        mean_classe0 += mean0
        mean_classe1 += mean1
        mean_classe2 += mean2
        mean_classe3 += mean3
        mean_classe4 += mean4
        mean_tot += mean5
        
    print(f"Class 0: {mean_classe0 / len(val_loader):.4f}")
    print(f"Class 1: {mean_classe1 / len(val_loader):.4f}")
    print(f"Class 2: {mean_classe2 / len(val_loader):.4f}")
    print(f"Class 3: {mean_classe3 / len(val_loader):.4f}")
    print(f"Class 4: {mean_classe4 / len(val_loader):.4f}")
    print(f"Class tot: {mean_tot / len(val_loader):.4f}")
    
    # Print the pixel counts for each class
    for c in range(cfg.DATA.NUM_CLASSES):
        if class_counts[c]==0 or c==0:
            class_counts[c]=1
        print(f"pixels {c}: {class_counts[c]} pixels")
  

    net.train()
    criterion.cuda()


if __name__ == '__main__':
    main()






