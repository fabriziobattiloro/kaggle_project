import os
import random

import torch
from torch import optim
from torch.autograd import Variable
from torch.nn import NLLLoss2d
from torch.optim.lr_scheduler import StepLR
from torchvision.utils import save_image
import torchvision.transforms as standard_transforms
import torchvision.utils as vutils
from tensorboardX import SummaryWriter

from models.icnet import ICNet
from models.config import cfg
from models.loading_data import loading_data
from models.utils import *
from models.timer import Timer
import pdb
from models.loss import ICNetLoss

exp_name = cfg.TRAIN.EXP_NAME
log_txt = cfg.TRAIN.EXP_LOG_PATH + '/' + exp_name + '.txt'
writer = SummaryWriter(cfg.TRAIN.EXP_PATH+ '/' + exp_name)

pil_to_tensor = standard_transforms.ToTensor()
train_loader, val_loader, restore_transform = loading_data()

def main():

    cfg_file = open('/kaggle/working/project-code1/binary/models/config.py',"r")  
    cfg_lines = cfg_file.readlines()
    
    with open(log_txt, 'a') as f:
            f.write(''.join(cfg_lines) + '\n\n\n\n')
    if len(cfg.TRAIN.GPU_ID)==1:
        torch.cuda.set_device(cfg.TRAIN.GPU_ID[0])
    torch.backends.cudnn.benchmark = True

    net = []   
    net = ICNet(cfg.DATA.NUM_CLASSES)

    if len(cfg.TRAIN.GPU_ID)>1:
        net = torch.nn.DataParallel(net, device_ids=cfg.TRAIN.GPU_ID).cuda()
    else:
        net=net.cuda()

    net.train()
    criterion = torch.nn.BCEWithLogitsLoss().cuda() # Binary Classification
    optimizer = optim.Adam(net.parameters(), lr=cfg.TRAIN.LR, weight_decay=cfg.TRAIN.WEIGHT_DECAY)
    scheduler = StepLR(optimizer, step_size=cfg.TRAIN.NUM_EPOCH_LR_DECAY, gamma=cfg.TRAIN.LR_DECAY)
    _t = {'train time' : Timer(),'val time' : Timer()} 
    validate(val_loader, net, criterion, optimizer, -1, restore_transform)
    for epoch in range(cfg.TRAIN.MAX_EPOCH):
        _t['train time'].tic()
        train(train_loader, net, criterion, optimizer, epoch)
        _t['train time'].toc(average=False)
        print('training time of one epoch: {:.2f}s'.format(_t['train time'].diff))
        _t['val time'].tic()
        validate(val_loader, net, criterion, optimizer, epoch, restore_transform)
        _t['val time'].toc(average=False)
        print('val time of one epoch: {:.2f}s'.format(_t['val time'].diff))


def train(train_loader, net, criterion, optimizer, epoch):
    for i, data in enumerate(train_loader, 0):
        inputs, labels = data
        inputs = Variable(inputs).cuda()
        labels = Variable(labels).cuda()
  
        outputs = net(inputs)
        out0, out1, out2, out3 = outputs

        loss0 = criterion(out0, labels.unsqueeze(1).float())
        #loss1 = criterion(out1, labels.unsqueeze(1).float())
        #loss2 = criterion(out2, labels.unsqueeze(1).float())
        #loss3 = criterion(out3, labels.unsqueeze(1).float())
        
        #loss= loss0+loss1+loss2+loss3

        # reduce losses over all GPUs for logging purposes
        optimizer.zero_grad()
        loss0.backward()
        optimizer.step()

def validate(val_loader, net, criterion, optimizer, epoch, restore):
    net.eval()
    criterion.cpu()
    input_batches = []
    output_batches = []
    label_batches = []
    iou_ = 0.0
    for vi, data in enumerate(val_loader, 0):
        inputs, labels = data
        inputs = Variable(inputs, volatile=True).cuda()
        labels = Variable(labels, volatile=True).cuda()
        outputs = net(inputs)
        out0, out1, out2, out3 = outputs
        #for binary classification
        out0[out0>0.5] = 1
        out0[out0<=0.5] = 0

        iou_ += calculate_mean_iu([out0.squeeze_(1).data.cpu().numpy()], [labels.data.cpu().numpy()], 2)
    mean_iu = iou_/len(val_loader) 
    flops, params = compute_flops(net)
    model_size = compute_model_size(net)


    print('[mean iu %.4f]' % (mean_iu)) 
    print('Model size %.4f' % (model_size))
    print("flops:"+flops)
    print("params:"+params)
    net.train()
    criterion.cuda() 

if __name__ == '__main__':
    main()








