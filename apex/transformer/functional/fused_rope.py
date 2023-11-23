# coding=utf-8
# Copyright (c) 2023, NVIDIA CORPORATION.  All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Tuple, Union
import torch


class FusedRoPEFunc(torch.autograd.Function):
    """
    Fused RoPE function
    
    This implementation assumes the input tensor to be in `sbhd` format and the RoPE tensor to be
    of shape (s, 1, 1, d). It accepts arbitrary memory layouts to avoid the expensive
    `.contiguous()` calls, thus it may not achieve the best memory access pattern.
    """

    @staticmethod
    def forward(
        ctx,
        t: torch.Tensor,
        cos_: torch.Tensor,
        sin_: torch.Tensor,
        transpose_output_memory: bool = False,
    ) -> torch.Tensor:
        import fused_rotary_positional_embedding

        output = fused_rotary_positional_embedding.forward(
            t, cos_, sin_, transpose_output_memory
        )
        ctx.save_for_backward(cos_, sin_)
        ctx.transpose_output_memory = transpose_output_memory

        return output

    @staticmethod
    def backward(
        ctx, grad_output: torch.Tensor
    ) -> Tuple[Union[torch.Tensor, None], ...]:
        import fused_rotary_positional_embedding

        cos_, sin_ = ctx.saved_tensors
        grad_input = fused_rotary_positional_embedding.backward(
            grad_output, cos_, sin_, ctx.transpose_output_memory
        )

        return grad_input, None, None, None


def fused_apply_rotary_pos_emb(
    t: torch.Tensor,
    freqs: torch.Tensor,
    transpose_output_memory: bool = False,
) -> torch.Tensor:
    """Apply rotary positional embedding to input tensor T.

    Args:
        t (Tensor): Input tensor T is of shape [seq_length, ... , dim]
        freqs (Tensor): Rotary Positional embedding tensor freq is of shape [seq_length, ..., dim]
        transpose_output_memory (bool): Default to False. Whether to transpose the 's' and 'b'
        dimension of the output's underlying memory format. This is very helpful when you want to
        get a contiguous tensor after calling `output.transpose(0, 1)`.

    Returns:
        Tensor: The input tensor after applying RoPE
    """
    cos_ = torch.cos(freqs)
    sin_ = torch.sin(freqs)
    return FusedRoPEFunc.apply(t, cos_, sin_, transpose_output_memory)


def fused_apply_rotary_pos_emb_cached(
    t: torch.Tensor,
    cos_: torch.Tensor,
    sin_: torch.Tensor,
    transpose_output_memory: bool = False,
) -> torch.Tensor:
    """Apply rotary positional embedding to input tensor T.

    Args:
        t (Tensor): Input tensor T is of shape [seq_length, ... , dim]
        cos (Tensor): Cached cosine of the rotary positional embedding tensor is of shape [seq_length, ..., dim]
        sin (Tensor): Cached sine of the rotary positional embedding tensor is of shape [seq_length, ..., dim]
        transpose_output_memory (bool): Default to False. Whether to transpose the 's' and 'b'
        dimension of the output's underlying memory format. This is very helpful when you want to
        get a contiguous tensor after calling `output.transpose(0, 1)`.

    Returns:
        Tensor: The input tensor after applying RoPE
    """
    return FusedRoPEFunc.apply(t, cos_, sin_, transpose_output_memory)
