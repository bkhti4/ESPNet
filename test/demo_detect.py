import numpy as np
import torch
from torch.autograd import Variable
import glob
import cv2
from PIL import Image as PILImage
import Model as Net
import os
import time
from argparse import ArgumentParser

pallete = [[128, 64, 128],
           [244, 35, 232],
           [70, 70, 70],
           [102, 102, 156],
           [190, 153, 153],
           [153, 153, 153],
           [250, 170, 30],
           [220, 220, 0],
           [107, 142, 35],
           [152, 251, 152],
           [70, 130, 180],
           [220, 20, 60],
           [255, 0, 0],
           [0, 0, 142],
           [0, 0, 70],
           [0, 60, 100],
           [0, 80, 100],
           [0, 0, 230],
           [119, 11, 32],
           [0, 0, 0]]


def relabel(img):
    '''
    This function relabels the predicted labels so that cityscape dataset can process
    :param img:
    :return:
    '''
    img[img == 19] = 255
    img[img == 18] = 33
    img[img == 17] = 32
    img[img == 16] = 31
    img[img == 15] = 28
    img[img == 14] = 27
    img[img == 13] = 26
    img[img == 12] = 25
    img[img == 11] = 24
    img[img == 10] = 23
    img[img == 9] = 22
    img[img == 8] = 21
    img[img == 7] = 20
    img[img == 6] = 19
    img[img == 5] = 17
    img[img == 4] = 13
    img[img == 3] = 12
    img[img == 2] = 11
    img[img == 1] = 8
    img[img == 0] = 7
    img[img == 255] = 0
    return img


def evaluateModel(args, model, up, vid_source):
    # gloabl mean and std values
    mean = [72.3923111, 82.90893555, 73.15840149]
    std = [45.3192215, 46.15289307, 44.91483307]

    cap = cv2.VideoCapture(vid_source)
    show_img = True

    times_infer, times_pipe = [], []

    while True:
        ret, img = cap.read()

        if ret == False:
          break

        if args.overlay:
            img_orig = np.copy(img)

        img = img.astype(np.float32)
        for j in range(3):
            img[:, :, j] -= mean[j]
        for j in range(3):
            img[:, :, j] /= std[j]

        # resize the image to 1024x512x3
        img = cv2.resize(img, (1024, 512))
        if args.overlay:
            img_orig = cv2.resize(img_orig, (1024, 512))

        img /= 255
        img = img.transpose((2, 0, 1))
        img_tensor = torch.from_numpy(img)
        img_tensor = torch.unsqueeze(img_tensor, 0)  # add a batch dimension
        img_variable = Variable(img_tensor)
        if args.gpu:
            img_variable = img_variable.cuda()

        t0 = time.time()
        with torch.no_grad():
          img_out = model(img_variable)
          
          if args.modelType == 2:
            img_out = up(img_out)

        classMap_numpy = img_out[0].max(0)[1].byte().cpu().data.numpy()
        t1 = time.time()

        if args.colored:
            classMap_numpy_color = np.zeros((img.shape[1], img.shape[2], img.shape[0]), dtype=np.uint8)
            for idx in range(len(pallete)):
                [r, g, b] = pallete[idx]
                classMap_numpy_color[classMap_numpy == idx] = [b, g, r]
            if args.overlay:
                overlayed = cv2.addWeighted(img_orig, 0.5, classMap_numpy_color, 0.5, 0)

        t2 = time.time()

        t1 = time.time()
        t2 = time.time()

        times_infer.append(t1-t0)
        times_pipe.append(t2-t0)
            
        times_infer = times_infer[-20:]
        times_pipe = times_pipe[-20:]

        ms = sum(times_infer)/len(times_infer)*1000
        fps_infer = 1000 / (ms+0.00001)
        fps_pipe = 1000 / (sum(times_pipe)/len(times_pipe)*1000)
            
        overlayed = cv2.putText(overlayed, "Time: {:.1f}FPS".format(fps_infer), (0, 30), cv2.FONT_HERSHEY_COMPLEX_SMALL, 1, (0, 0, 255), 2)

        print("Time: {:.2f}ms, Detection FPS: {:.1f}, total FPS: {:.1f}".format(ms, fps_infer, fps_pipe))

        if show_img:
          cv2.imshow(args.model, overlayed)
          if cv2.waitKey(1) & 0xFF == ord("q"):
            cv2.destroyAllWindows()
            break
    cap.release()


def main(args):
    up = None
    if args.modelType == 2:
        up = torch.nn.Upsample(scale_factor=8, mode='bilinear')
        if args.gpu:
            up = up.cuda()

    p = args.p
    q = args.q
    classes = args.classes
    if args.modelType == 2:
        modelA = Net.ESPNet_Encoder(classes, p, q)  # Net.Mobile_SegNetDilatedIA_C_stage1(20)
        model_weight_file = args.weightsDir + os.sep + 'encoder' + os.sep + 'espnet_p_' + str(p) + '_q_' + str(
            q) + '.pth'
        if not os.path.isfile(model_weight_file):
            print('Pre-trained model file does not exist. Please check ../pretrained/encoder folder')
            exit(-1)
        modelA.load_state_dict(torch.load(model_weight_file))
    elif args.modelType == 1:
        modelA = Net.ESPNet(classes, p, q)  # Net.Mobile_SegNetDilatedIA_C_stage1(20)
        model_weight_file = args.weightsDir + os.sep + 'decoder' + os.sep + 'espnet_p_' + str(p) + '_q_' + str(q) + '.pth'
        if not os.path.isfile(model_weight_file):
            print('Pre-trained model file does not exist. Please check ../pretrained/decoder folder')
            exit(-1)
        modelA.load_state_dict(torch.load(model_weight_file))
    else:
        print('Model not supported')
    # modelA = torch.nn.DataParallel(modelA)
    if args.gpu:
        modelA = modelA.cuda()

    # set to evaluation mode
    modelA.eval()

    #if not os.path.isdir(args.savedir):
    #    os.mkdir(args.savedir)

    evaluateModel(args, modelA, up, args.source)


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--model', default="ESPNet-C", help='Model name')
    parser.add_argument('--source', default="./data/challenge.mp4", help='Data directory')
    parser.add_argument('--inWidth', type=int, default=1024, help='Width of RGB image')
    parser.add_argument('--inHeight', type=int, default=512, help='Height of RGB image')
    parser.add_argument('--scaleIn', type=int, default=8, help='For ESPNet-C, scaleIn=8. For ESPNet, scaleIn=1')
    parser.add_argument('--modelType', type=int, default=2, help='1=ESPNet, 2=ESPNet-C')
    parser.add_argument('--gpu', default=True, type=bool, help='Run on CPU or GPU. If TRUE, then GPU.')
    parser.add_argument('--decoder', type=bool, default=False,
                        help='True if ESPNet. False for ESPNet-C')  # False for encoder
    parser.add_argument('--weightsDir', default='../pretrained/', help='Pretrained weights directory.')
    parser.add_argument('--p', default=2, type=int, help='depth multiplier. Supported only 2')
    parser.add_argument('--q', default=8, type=int, help='depth multiplier. Supported only 3, 5, 8')
    parser.add_argument('--cityFormat', default=True, type=bool, help='If you want to convert to cityscape '
                                                                       'original label ids')
    parser.add_argument('--colored', default=True, type=bool, help='If you want to visualize the '
                                                                   'segmentation masks in color')
    parser.add_argument('--overlay', default=True, type=bool, help='If you want to visualize the '
                                                                   'segmentation masks overlayed on top of RGB image')
    parser.add_argument('--classes', default=20, type=int, help='Number of classes in the dataset. 20 for Cityscapes')

    args = parser.parse_args()
    #assert (args.modelType == 1) and args.decoder, 'Model type should be 2 for ESPNet-C and 1 for ESPNet'
    if args.overlay:
        args.colored = True # This has to be true if you want to overlay
    main(args)