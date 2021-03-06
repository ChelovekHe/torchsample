
import os
import random
import math
import numpy as np

import torch as th
from torch.autograd import Variable

class Compose(object):
    """
    Composes several transforms together.

    Args:
        transforms (List[Transform]): list of transforms to compose.

    Example:
        >>> transforms.Compose([
        >>>     transforms.CenterCrop(10),
        >>>     transforms.ToTensor(),
        >>> ])
    """
    def __init__(self, transforms):
        self.transforms = transforms

    def __call__(self, x, y=None):
        if y is not None:
            for t in self.transforms:
                x, y = t(x, y)
            return x, y
        else:
            for t in self.transforms:
                x = t(x)
            return x


class ToTensor(object):
    """
    Converts a numpy array to th.Tensor
    """
    
    def __call__(self, x, y=None):
        x = th.from_numpy(x)
        if y is not None:
            y = th.from_numpy(y)
            return x, y
        return x


class ToVariable(object):

    def __call__(self, x, y=None):
        x = Variable(x)
        if y is not None:
            y = Variable(y)
            return x, y
        return x


class ToCuda(object):

    def __init__(self, device=0):
        self.device = device

    def __call__(self, x, y):
        x = x.cuda(self.device)
        if y is not None:
            y = y.cuda(self.device)
            return x, y
        else:
            return x


class ToFile(object):
    """
    Saves an image to file. Useful as the last transform
    when wanting to observe how augmentation/affine transforms
    are affecting the data
    """
    def __init__(self, root, save_format='npy'):
        """Save image to file

        Arguments
        ---------
        root : string
            path to main directory in which images will be saved

        save_format : string in `{'npy', 'jpg', 'png'}
            file format in which to save the sample. Right now, only
            numpy's `npy` format is supported
        """
        self.root = root
        self.save_format = save_format
        self.counter = 0

    def __call__(self, x, y=None):
        np.save(os.path.join(self.root,'x_img-%i.npy'%self.counter), x.numpy())
        if y is not None:
            np.save(os.path.join(self.root,'y_img-%i.npy'%self.counter), y.numpy())
            self.counter += 1
            return x, y
        else:
            self.counter += 1
            return x


class ChannelsLast(object):

    def __init__(self, safe_check=False):
        self.safe_check = safe_check

    def __call__(self, x, y=None):
        ndim = x.dim()
        if self.safe_check:
            # check if channels are already last
            if x.size(-1) < x.size(0):
                if y is not None:
                    return x, y
                return x
        plist = list(range(1,ndim))+[0]
        x = x.permute(*plist)
        if y is not None:
            y = y.permute(*plist)
            return x, y
        return x

HWC = ChannelsLast
DHWC = ChannelsLast

class ChannelsFirst(object):

    def __init__(self, safe_check=False):
        self.safe_check = safe_check

    def __call__(self, x, y=None):
        ndim = x.dim()
        if self.safe_check:
            # check if channels are already first
            if x.size(0) < x.size(-1):
                if y is not None:
                    return x, y
                return x
        plist = [ndim-1] + list(range(0,ndim-1))
        x = x.permute(*plist)
        if y is not None:
            y = y.permute(*plist)
            return x, y
        return x

CHW = ChannelsFirst
CDHW = ChannelsFirst

class TypeCast(object):

    def __init__(self, dtype='float'):
        if isinstance(dtype, str):
            if dtype == 'byte':
                dtype = th.ByteTensor
            elif dtype == 'double':
                dtype = th.DoubleTensor
            elif dtype == 'float':
                dtype = th.FloatTensor
            elif dtype == 'int':
                dtype = th.Intensor
            elif dtype == 'long':
                dtype = th.LongTensor
            elif dtype == 'short':
                dtype = th.ShortTensor
        self.dtype = dtype

    def __call__(self, x, y=None):
        x = x.type(self.dtype)
        if y is not None:
            y = y.type(self.dtype)
            return x, y
        return x


class AddChannel(object):
    """
    Adds a dummy channel to an image. 
    This will make an image of size (28, 28) to now be
    of size (1, 28, 28), for example.
    """
    def __init__(self, axis=0):
        self.axis = axis

    def __call__(self, x, y=None):
        x = x.unsqueeze(self.axis)
        if y is not None:
            y = y.unsqueeze(self.axis)
            return x,y
        return x


class Transpose(object):

    def __init__(self, dim1, dim2):
        self.dim1 = dim1
        self.dim2 = dim2

    def __call__(self, x, y=None):
        x = th.transpose(x, self.dim1, self.dim2)
        if y is not None:
            y = th.transpose(y, self.dim1, self.dim2)
            return x, y
        else:
            return x


class RangeNormalize(object):
    """
    Given min_val: (R, G, B) and max_val: (R,G,B),
    will normalize each channel of the th.*Tensor to
    the provided min and max values.

    Works by calculating :
        a = (max'-min')/(max-min)
        b = max' - a * max
        new_value = a * value + b
    where min' & max' are given values, 
    and min & max are observed min/max for each channel
    
    Arguments
    ---------
    min_range : float or integer
        Min value to which tensors will be normalized
    max_range : float or integer
        Max value to which tensors will be normalized
    fixed_min : float or integer
        Give this value if every sample has the same min (max) and 
        you know for sure what it is. For instance, if you
        have an image then you know the min value will be 0 and the
        max value will be 255. Otherwise, the min/max value will be
        calculated for each individual sample and this will decrease
        speed. Dont use this if each sample has a different min/max.
    fixed_max :float or integer
        See above

    Example:
        >>> x = th.rand(3,5,5)
        >>> rn = RangeNormalize((0,0,10),(1,1,11))
        >>> x_norm = rn(x)

    Also works with just one value for min/max:
        >>> x = th.rand(3,5,5)
        >>> rn = RangeNormalize(0,1)
        >>> x_norm = rn(x)
    """
    def __init__(self, 
                 min_range, 
                 max_range, 
                 fixed_min=None, 
                 fixed_max=None):
        self.min_range = min_range
        self.max_range = max_range
        self.fixed_min = fixed_min
        self.fixed_max = fixed_max

    def __call__(self, x, y=None):
        if self.fixed_min is not None:
            min_val = self.fixed_min
        else:
            min_val = th.min(x)
        if self.fixed_max is not None:
            max_val = self.fixed_max
        else:
            max_val = th.max(x)
        if min_val == max_val:
            min_val += 1e-07

        a = (self.max_range - self.min_range) / (max_val - min_val)
        b = self.max_range - a * max_val
        x_norm = x.mul(a).add(b)
        if y is None:
            return x_norm
        else:
            min_val = th.min(y)
            max_val = th.max(y)
            a = (self.max_range - self.min_range) / (max_val - min_val)
            b = self.max_range - a * max_val
            y_norm = y.mul(a).add(b)
            return x_norm, y_norm


class UnitRange(object):
    """
    Normalize tensor to be between zero and one
    """
    def __call__(self, x, y=None):
        x = x.sub(x.min()).div(x.max()-x.min())
        if y is not None:
            y = y.sub(y.min()).div(y.max()-y.min())
            return x, y
        return x


class StdNormalize(object):
    """
    Normalize torch tensor to have zero mean and unit std deviation
    """

    def __init__(self):
        pass

    def __call__(self, x, y=None):
        if y is not None:
            for t, u in zip(x, y):
                t.sub_(th.mean(t)).div_(th.std(t))
                u.sub_(th.mean(u)).div_(th.std(u))
            return x, y
        else:
            for t in x:
                t.sub_(th.mean(t)).div_(th.std(t))
            return x         


class Slice2D(object):

    def __init__(self, axis=0, reject_zeros=False):
        """
        Take a random 2D slice from a 3D image along 
        a given axis. This image should not have a 4th channel dim.

        Arguments
        ---------
        axis : integer in {0, 1, 2}
            the axis on which to take slices

        reject_zeros : boolean
            whether to reject slices that are all zeros
        """
        self.axis = axis
        self.reject_zeros = reject_zeros

    def __call__(self, x, y=None):
        while True:
            keep_slice  = random.randint(0,x.size(self.axis)-1)
            if self.axis == 0:
                slice_x = x[keep_slice,:,:]
                if y is not None:
                    slice_y = y[keep_slice,:,:]
            elif self.axis == 1:
                slice_x = x[:,keep_slice,:]
                if y is not None:
                    slice_y = y[:,keep_slice,:]
            elif self.axis == 2:
                slice_x = x[:,:,keep_slice]
                if y is not None:
                    slice_y = y[:,:,keep_slice]

            if not self.reject_zeros:
                break
            else:
                if y is not None and th.sum(slice_y) > 0:
                        break
                elif th.sum(slice_x) > 0:
                        break
        if y is not None:
            return slice_x, slice_y
        else:
            return slice_x


class RandomCrop(object):

    def __init__(self, crop_size):
        """
        Randomly crop a torch tensor

        Arguments
        --------
        size : tuple or list
            dimensions of the crop
        """
        self.crop_size = crop_size

    def __call__(self, x, y=None):
        h_idx = random.randint(0,x.size(1)-self.crop_size[0])
        w_idx = random.randint(0,x.size(2)-self.crop_size[1])
        x = x[:, h_idx:(h_idx+self.crop_size[0]),w_idx:(w_idx+self.crop_size[1])]
        if y is not None:
            y = y[:, h_idx:(h_idx+self.crop_size[0]),w_idx:(w_idx+self.crop_size[1])] 
            return x, y
        else:
            return x


class SpecialCrop(object):

    def __init__(self, crop_size, crop_type=0):
        """
        Perform a special crop - one of the four corners or center crop

        Arguments
        ---------
        crop_type : integer in {0,1,2,3,4}
            0 = center crop
            1 = top left crop
            2 = top right crop
            3 = bottom right crop
            4 = bottom left crop
        """
        if crop_type not in {0, 1, 2, 3, 4}:
            raise ValueError('crop_type must be in {0, 1, 2, 3, 4}')
        self.crop_size = crop_size
        self.crop_type = crop_type
    
    def __call__(self, x, y=None):
        if self.crop_type == 0:
            # center crop
            x_diff  = (x.size(1)-self.crop_size[0])/2.
            y_diff  = (x.size(2)-self.crop_size[1])/2.
            ct_x    = [int(math.ceil(x_diff)),x.size(1)-int(math.floor(x_diff))]
            ct_y    = [int(math.ceil(y_diff)),x.size(2)-int(math.floor(y_diff))]
            indices = [ct_x,ct_y]        
        elif self.crop_type == 1:
            # top left crop
            tl_x = [0, self.crop_size[0]]
            tl_y = [0, self.crop_size[1]]
            indices = [tl_x,tl_y]
        elif self.crop_type == 2:
            # top right crop
            tr_x = [0, self.crop_size[0]]
            tr_y = [x.size(2)-self.crop_size[1], x.size(2)]
            indices = [tr_x,tr_y]
        elif self.crop_type == 3:
            # bottom right crop
            br_x = [x.size(1)-self.crop_size[0],x.size(1)]
            br_y = [x.size(2)-self.crop_size[1],x.size(2)]
            indices = [br_x,br_y]
        elif self.crop_type == 4:
            # bottom left crop
            bl_x = [x.size(1)-self.crop_size[0], x.size(1)]
            bl_y = [0, self.crop_size[1]]
            indices = [bl_x,bl_y]
        
        x = x[:,indices[0][0]:indices[0][1],indices[1][0]:indices[1][1]]

        if y is not None:
            y = y[:,indices[0][0]:indices[0][1],indices[1][0]:indices[1][1]]
            return x, y
        else:
            return x


class Pad(object):

    def __init__(self, size):
        """
        Pads an image to the given size
        """
        self.size = size

    def __call__(self, x, y=None):
        x = x.numpy()
        shape_diffs = [int(np.ceil((i_s - d_s))) for d_s,i_s in zip(x.shape,self.size)]
        shape_diffs = np.maximum(shape_diffs,0)
        pad_sizes = [(int(np.ceil(s/2.)),int(np.floor(s/2.))) for s in shape_diffs]
        x = np.pad(x, pad_sizes, mode='constant')
        if y is not None:
            y = y.numpy()
            y = np.pad(y, pad_sizes, mode='constant')
            return th.from_numpy(x), th.from_numpy(y)
        else:
            return th.from_numpy(x)


class RandomFlip(object):

    def __init__(self, h=True, v=False, p=0.5):
        """
        Randomly flip an image horizontally and/or vertically with
        some probability.

        Arguments
        ---------
        h : boolean
            whether to horizontally flip w/ probability p

        v : boolean
            whether to vertically flip w/ probability p

        p : float between [0,1]
            probability with which to apply allowed flipping operations
        """
        self.horizontal = h
        self.vertical = v
        self.p = p

    def __call__(self, x, y=None):
        x = x.numpy()
        if y is not None:
            y = y.numpy()
        # horizontal flip with p = self.p
        if self.horizontal:
            if random.random() < self.p:
                x = x.swapaxes(2, 0)
                x = x[::-1, ...]
                x = x.swapaxes(0, 2)
                if y is not None:
                    y = y.swapaxes(2, 0)
                    y = y[::-1, ...]
                    y = y.swapaxes(0, 2)
        # vertical flip with p = self.p
        if self.vertical:
            if random.random() < self.p:
                x = x.swapaxes(1, 0)
                x = x[::-1, ...]
                x = x.swapaxes(0, 1)
                if y is not None:
                    y = y.swapaxes(1, 0)
                    y = y[::-1, ...]
                    y = y.swapaxes(0, 1)
        if y is None:
            # must copy because torch doesnt current support neg strides
            return th.from_numpy(x.copy())
        else:
            return th.from_numpy(x.copy()),th.from_numpy(y.copy())


class RandomOrder(object):
    """
    Randomly permute the image channels
    """
    def __call__(self, x, y=None):
        order = th.randperm(x.dim())
        x = x.index_select(0, order)
        if y is not None:
            y = y.index_select(0, order)
        return x, y

