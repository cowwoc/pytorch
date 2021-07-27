# -*- coding: utf-8 -*-

import logging

import torch
from torch import nn
from torch.ao.sparsity import BasePruner, PruningParametrization
from torch.nn.utils import parametrize

from torch.testing._internal.common_utils import TestCase

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

class Linear(nn.Module):
    def __init__(self):
        super().__init__()
        self.seq = nn.Sequential(
            nn.Linear(16, 16, bias=False)
        )
        self.linear = nn.Linear(16, 16, bias=False)

    def forward(self, x):
        x = self.seq(x)
        x = self.linear(x)
        return x


class LinearB(nn.Module):
    def __init__(self):
        super().__init__()
        self.seq = nn.Sequential(
            nn.Linear(16, 16, bias=True)
        )
        self.linear = nn.Linear(16, 16, bias=True)

    def forward(self, x):
        x = self.seq(x)
        x = self.linear(x)
        return x


class MultipleLinear(nn.Module):
    def __init__(self):
        super().__init__()
        self.seq = nn.Sequential(
            nn.Linear(7, 5, bias=False),
            nn.ReLU(),
            nn.Linear(5, 8, bias=False),
            nn.ReLU(),
            nn.Linear(8, 6, bias=False)
        )
        self.linear = nn.Linear(6, 4, bias=False)

    def forward(self, x):
        x = self.seq(x)
        x = self.linear(x)
        return x


class MultipleLinearB(nn.Module):
    def __init__(self):
        super().__init__()
        self.seq = nn.Sequential(
            nn.Linear(7, 5, bias=True),
            nn.ReLU(),
            nn.Linear(5, 8, bias=True),
            nn.ReLU(),
            nn.Linear(8, 6, bias=True)
        )
        self.linear = nn.Linear(6, 4, bias=True)

    def forward(self, x):
        x = self.seq(x)
        x = self.linear(x)
        return x


class MultipleLinearMixed(nn.Module):
    def __init__(self):
        super().__init__()
        self.seq = nn.Sequential(
            nn.Linear(7, 5, bias=True),
            nn.ReLU(),
            nn.Linear(5, 8, bias=False),
            nn.ReLU(),
            nn.Linear(8, 6, bias=True)
        )
        self.linear = nn.Linear(6, 4, bias=False)

    def forward(self, x):
        x = self.seq(x)
        x = self.linear(x)
        return x


class Conv2d(nn.Module):
    def __init__(self):
        super().__init__()
        self.seq = nn.Sequential(
            nn.Conv2d(1, 32, 3, 1, bias=False),
        )
        self.conv2d = nn.Conv2d(32, 64, 3, 1, bias=False)

    def forward(self, x):
        x = self.seq(x)
        x = self.conv2d(x)
        return x


class SimplePruner(BasePruner):
    def update_mask(self, layer, **kwargs):
        layer.parametrizations.weight[0].pruned_outputs.add(1)


class MultiplePruner(BasePruner):
    def update_mask(self, layer, **kwargs):
        layer.parametrizations.weight[0].pruned_outputs.update([1, 2])


class TestBasePruner(TestCase):

    def _test_constructor_on_device(self, device):
        print(f'Testing on {device.type}')

        self.assertRaisesRegex(TypeError, 'with abstract methods update_mask',
                               BasePruner)
        # Can instantiate the model with no configs
        model = Linear()
        model = model.to(device)
        pruner = SimplePruner(model, None, None)
        for g in pruner.module_groups:
            module = g['module']
            assert module.weight.device == device
        assert len(pruner.module_groups) == 2
        pruner.step()
        # Can instantiate the model with configs
        pruner = SimplePruner(model, [model.linear], {'test': 3})
        assert len(pruner.module_groups) == 1
        assert pruner.module_groups[0]['path'] == 'linear'
        assert 'test' in pruner.module_groups[0]
        assert pruner.module_groups[0]['test'] == 3

    def test_constructor(self):
        self._test_constructor_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_constructor_on_device(torch.device('cuda'))

    def _test_prepare_linear_on_device(self, device):
        print(f'Testing on {device.type}')

        model = Linear()
        model = model.to(device)
        x = torch.ones(128, 16)
        pruner = SimplePruner(model, None, None)
        pruner.prepare()
        for g in pruner.module_groups:
            module = g['module']
            assert module.weight.device == device
            # Check mask exists
            assert hasattr(module, 'mask')
            # Check parametrization exists and is correct
            assert parametrize.is_parametrized(module)
            assert hasattr(module, "parametrizations")
            # Assume that this is the 1st/only parametrization
            assert type(module.parametrizations.weight[0]) == PruningParametrization
        assert model(x).shape == (128, 16)

    def test_prepare_linear(self):
        self._test_prepare_linear_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_prepare_linear_on_device(torch.device('cuda'))

    def _test_prepare_conv2d_on_device(self, device):
        print(f'Testing on {device.type}')
        model = Conv2d()
        model = model.to(device)
        x = torch.ones((1, 1, 28, 28))
        pruner = SimplePruner(model, None, None)
        pruner.prepare()
        for g in pruner.module_groups:
            module = g['module']
            assert module.weight.device == device
            # Check mask exists
            assert hasattr(module, 'mask')
            # Check parametrization exists and is correct
            assert parametrize.is_parametrized(module)
            assert hasattr(module, "parametrizations")
            # Assume that this is the 1st/only parametrization
            assert type(module.parametrizations.weight[0]) == PruningParametrization
        assert model(x).shape == (1, 64, 24, 24)

    def test_prepare_conv2d(self):
        self._test_prepare_conv2d_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_prepare_conv2d_on_device(torch.device('cuda'))

    def _test_prepare_linear_bias_on_device(self, device):
        print(f'Testing on {device.type}')
        model = LinearB()
        model = model.to(device)
        x = torch.ones(128, 16)
        pruner = SimplePruner(model, None, None)
        pruner.prepare()
        for g in pruner.module_groups:
            module = g['module']
            assert module.weight.device == device
            # Check mask exists
            assert hasattr(module, 'mask')
            # Check parametrization exists and is correct
            assert parametrize.is_parametrized(module)
            assert hasattr(module, "parametrizations")
            # Assume that this is the 1st/only parametrization
            assert type(module.parametrizations.weight[0]) == PruningParametrization
        assert model(x).shape == (128, 16)

    def test_prepare_linear_bias(self):
        self._test_prepare_linear_bias_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_prepare_linear_bias_on_device(torch.device('cuda'))

    def _test_convert_linear_on_device(self, device):
        print(f'Testing on {device.type}')
        model = Linear()
        model = model.to(device)
        x = torch.ones(128, 16)
        pruner = SimplePruner(model, None, None)
        pruner.prepare()
        pruner.convert()
        for g in pruner.module_groups:
            module = g['module']
            assert module.weight.device == device
            assert not hasattr(module, "parametrizations")
            assert not hasattr(module, 'mask')
        assert model(x).shape == (128, 16)

    def test_convert_linear(self):
        self._test_convert_linear_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_convert_linear_on_device(torch.device('cuda'))

    def _test_convert_linear_bias_on_device(self, device):
        print(f'Testing on {device.type}')
        model = LinearB()
        model = model.to(device)
        x = torch.ones(128, 16)
        pruner = SimplePruner(model, None, None)
        pruner.prepare()
        pruner.convert()
        for g in pruner.module_groups:
            module = g['module']
            assert module.weight.device == device
            assert not hasattr(module, "parametrizations")
            assert not hasattr(module, 'mask')
        assert model(x).shape == (128, 16)

    def test_convert_linear_bias(self):
        self._test_convert_linear_bias_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_convert_linear_bias_on_device(torch.device('cuda'))

    def _test_convert_conv2d_on_device(self, device):
        print(f'Testing on {device.type}')
        model = Conv2d()
        model = model.to(device)
        x = torch.ones((1, 1, 28, 28))
        pruner = SimplePruner(model, None, None)
        pruner.prepare()
        pruner.convert()
        for g in pruner.module_groups:
            module = g['module']
            assert module.weight.device == device
            assert not hasattr(module, "parametrizations")
            assert not hasattr(module, 'mask')
        assert model(x).shape == (1, 64, 24, 24)

    def test_convert_conv2d(self):
        self._test_convert_conv2d_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_convert_conv2d_on_device(torch.device('cuda'))

    def _test_step_linear_on_device(self, device):
        print(f'Testing on {device.type}')
        model = Linear()
        model = model.to(device)
        x = torch.ones(16, 16)
        pruner = SimplePruner(model, None, None)
        pruner.prepare()
        pruner.enable_mask_update = True
        for g in pruner.module_groups:
            # Before step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set()
        pruner.step()
        for g in pruner.module_groups:
            # After step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set({1})
            assert not (False in (model(x)[:, 1] == 0))

        model = MultipleLinear()
        model = model.to(device)
        x = torch.ones(7, 7)
        pruner = MultiplePruner(model, None, None)
        pruner.prepare()
        pruner.enable_mask_update = True
        for g in pruner.module_groups:
            # Before step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set()
        pruner.step()
        for g in pruner.module_groups:
            # After step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set({1, 2})
            assert not (False in (model(x)[:, 1] == 0))
            assert not (False in (model(x)[:, 2] == 0))

    def test_step_linear(self):
        self._test_step_linear_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_step_linear_on_device(torch.device('cuda'))

    def _test_step_conv2d_on_device(self, device):
        print(f'Testing on {device.type}')
        model = Conv2d()
        model = model.to(device)
        x = torch.ones((1, 1, 28, 28))
        pruner = SimplePruner(model, None, None)
        pruner.prepare()
        pruner.enable_mask_update = True
        for g in pruner.module_groups:
            # Before step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set()
        pruner.step()
        for g in pruner.module_groups:
            # After step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set({1})
            assert not (False in (model(x)[:, 1, :, :] == 0))
        assert model(x).shape == (1, 64, 24, 24)

    def test_step_conv2d(self):
        self._test_step_conv2d_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_step_conv2d_on_device(torch.device('cuda'))

    def _test_step_linear_bias_on_device(self, device):
        print(f'Testing on {device.type}')
        model = LinearB()
        model = model.to(device)
        x = torch.ones(16, 16)
        pruner = SimplePruner(model, None, None)
        pruner.prepare()
        pruner.enable_mask_update = True
        for g in pruner.module_groups:
            # Before step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set()
        pruner.step()
        for g in pruner.module_groups:
            # After step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set({1})

        model = MultipleLinearB()
        model = model.to(device)
        x = torch.ones(7, 7)
        pruner = MultiplePruner(model, None, None)
        pruner.prepare()
        pruner.enable_mask_update = True
        for g in pruner.module_groups:
            # Before step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set()
        pruner.step()
        for g in pruner.module_groups:
            # After step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set({1, 2})

        model = MultipleLinearMixed()
        model = model.to(device)
        x = torch.ones(7, 7)
        pruner = MultiplePruner(model, None, None)
        pruner.prepare()
        pruner.enable_mask_update = True
        for g in pruner.module_groups:
            # Before step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set()
        pruner.step()
        for g in pruner.module_groups:
            # After step
            module = g['module']
            assert module.weight.device == device
            assert module.parametrizations.weight[0].pruned_outputs == set({1, 2})

    def test_step_linear_bias_linear(self):
        self._test_step_linear_bias_on_device(torch.device('cpu'))
        if torch.cuda.is_available():
            self._test_step_linear_bias_on_device(torch.device('cuda'))
