import torch
from torch.distributed._sharding_spec import ShardingSpec
from .api import (
    ShardedTensor,
    load_with_process_group
)

def empty(
        sharding_spec: ShardingSpec,
        *size,
        dtype=None,
        layout=torch.strided,
        requires_grad=False,
        pin_memory=False,
        memory_format=torch.contiguous_format,
        process_group=None,):
    """
    Creates an empty :class:`ShardedTensor`. Needs to be called on all ranks in an SPMD fashion.

    Args:
        sharding_spec (:class:`torch.distributed._sharding_spec.ShardingSpec): The specification
            describing how to shard the Tensor.
        size (int...): a sequence of integers defining the shape of the output
            tensor. Can be a variable number of arguments or a collection like a list or tuple.

    Keyword args:
        dtype (:class:`torch.dtype`, optional): the desired data type of returned tensor.
            Default: if ``None``, uses a global default (see :func:`torch.set_default_tensor_type`).
        layout (:class:`torch.layout`, optional): the desired layout of returned Tensor.
            Default: ``torch.strided``.
        requires_grad (bool, optional): If autograd should record operations on the
            returned tensor. Default: ``False``.
        pin_memory (bool, optional): If set, returned tensor would be allocated in
            the pinned memory. Works only for CPU tensors. Default: ``False``.
        memory_format (:class:`torch.memory_format`, optional): the desired memory format of
            returned Tensor. Default: ``torch.contiguous_format``.
        process_group (ProcessGroup, optional): The process group to work on. If None,
            the default process group will be used.

    Returns:
        A :class:`ShardedTensor` object on each rank
    """
    return ShardedTensor(
        sharding_spec,
        *size,
        dtype=dtype,
        layout=layout,
        requires_grad=requires_grad,
        pin_memory=pin_memory,
        memory_format=memory_format,
        process_group=process_group)

def state_dict_hook(module, destination, prefix, local_metadata):
    """
    Hook to add ShardedTensor to Module's ``state_dict``. Needs to be
    registered to the Module using
    :meth:`torch.nn.Module._register_state_dict_hook`.
    """
    _recurse_update_dict(module, destination, prefix)

def pre_load_state_dict_hook(module, state_dict, prefix, local_metadata, strict, missing_keys, unexpected_keys, error_msgs):
    """
    Pre-load state dict hook to add ShardedTensor to the module.
    """
    _recurse_update_module(module, state_dict, prefix)

def _recurse_update_module(module, state_dict, prefix):
    for attr_name, attr in module.__dict__.items():
        key = prefix + attr_name
        if key in state_dict:
            if isinstance(state_dict[key], ShardedTensor):
                setattr(module, attr_name, state_dict[key])

    for submodule_name, submodule in module.named_modules():
        key = prefix + submodule_name
        if submodule_name:
            _recurse_update_module(submodule, state_dict, key + '.')


def _recurse_update_dict(module, destination, prefix):
    for attr_name, attr in module.__dict__.items():
        if isinstance(attr, ShardedTensor):
            destination[prefix + attr_name] = attr

    for submodule_name, submodule in module.named_modules():
        if submodule_name != '':
            _recurse_update_dict(submodule, destination, prefix + submodule_name + '.')
