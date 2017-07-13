""" $lic$
Copyright (C) 2016-2017 by The Board of Trustees of Stanford University

This program is free software: you can redistribute it and/or modify it under
the terms of the Modified BSD-3 License as published by the Open Source
Initiative.

If you use this program in your research, we request that you reference the
TETRIS paper ("TETRIS: Scalable and Efficient Neural Network Acceleration with
3D Memory", in ASPLOS'17. April, 2017), and that you send us a citation of your
work.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE. See the BSD-3 License for more details.

You should have received a copy of the Modified BSD-3 License along with this
program. If not, see <https://opensource.org/licenses/BSD-3-Clause>.
"""

import itertools
import unittest

from nn_dataflow import BufShrScheme
from nn_dataflow import ConvLayer, PoolingLayer
from nn_dataflow import Cost
from nn_dataflow import DataCategoryEnum as de
from nn_dataflow import LoopBlockingScheme
from nn_dataflow import LoopEnum as le
from nn_dataflow import MapStrategyEyeriss
from nn_dataflow import MemHierEnum as me
from nn_dataflow import NestedLoopDesc
from nn_dataflow import NodeRegion
from nn_dataflow import Option
from nn_dataflow import ParallelEnum as pe
from nn_dataflow import Partition
from nn_dataflow import PartitionScheme
from nn_dataflow import PhyDim2
from nn_dataflow import Resource
from nn_dataflow import Util

class TestLoopBlockingFixture(unittest.TestCase):
    ''' Base fixture class for LoopBlocking tests. '''
    # pylint: disable=too-many-instance-attributes

    def setUp(self):

        # Workload.
        self.layer = {}
        self.layer['BASE'] = ConvLayer(12, 10, 28, 3)
        self.layer['POOL'] = PoolingLayer(32, 28, 2)
        self.layer['PAR'] = ConvLayer(24, 20, 56, 3)
        self.batch_size = 4

        # Resource.
        self.resource = {}
        dim_array = PhyDim2(16, 16)
        mem_regions = (NodeRegion(origin=PhyDim2(0, 0), dim=PhyDim2(1, 1)),)
        # Typical resource.
        self.resource['BASE'] = Resource(
            dim_nodes=PhyDim2(1, 1), dim_array=dim_array,
            mem_regions=mem_regions, size_gbuf=65536, size_regf=64)
        # Larger resource with sufficient capacity, to make all schemes valid.
        self.resource['LG'] = Resource(
            dim_nodes=PhyDim2(1, 1), dim_array=dim_array,
            mem_regions=mem_regions, size_gbuf=1024 ** 3, size_regf=1024 ** 3)
        # Small resource.
        self.resource['SM'] = Resource(
            dim_nodes=PhyDim2(1, 1), dim_array=dim_array,
            mem_regions=mem_regions, size_gbuf=4096, size_regf=16)
        # Multi-node parallel resource.
        self.resource['PAR'] = Resource(
            dim_nodes=PhyDim2(4, 2), dim_array=dim_array,
            mem_regions=mem_regions, size_gbuf=65535, size_regf=64)

        # Nested loop description after mapping.
        self.nld = {}
        self.nld['BASE'] = next(MapStrategyEyeriss(self.layer['BASE'],
                                                   self.batch_size, dim_array)
                                .gen_nested_loop_desc())
        self.nld['POOL'] = next(MapStrategyEyeriss(self.layer['POOL'],
                                                   self.batch_size, dim_array)
                                .gen_nested_loop_desc())
        # Fake nested loop, with zero ifmap size.
        self.nld['ZERO'] = NestedLoopDesc(loopcnt=(12, 10, 4),
                                          usize_gbuf=(9, 0, 800),
                                          usize_regf=(3, 0, 1),
                                          unit_access=((9, 0, 800), (9, 0, 800),
                                                       (3, 9, 7), (1, 1, 1)),
                                          unit_ops=1, unit_time=1)

        # Fake partition scheme.
        self.part = PartitionScheme(range(pe.NUM), ((1, 1),) * pe.NUM)

        # Fake buffer sharing scheme.
        self.bufshr = BufShrScheme(self.part)

        # Options.
        self.options = {}
        # Basic.
        self.options['BASE'] = Option(
            sw_gbuf_bypass=(False,) * 3, sw_solve_loopblocking=False,
            hw_access_forwarding=False, hw_gbuf_sharing=False,
            partition_hybrid=None, partition_batch=None, partition_ifmaps=None,
            ntops=2 ** 30, nprocesses=1, verbose=False)
        # Multiprocessing.
        self.options['MP'] = Option(
            sw_gbuf_bypass=(False,) * 3, sw_solve_loopblocking=False,
            hw_access_forwarding=False, hw_gbuf_sharing=False,
            partition_hybrid=None, partition_batch=None, partition_ifmaps=None,
            ntops=2 ** 30, nprocesses=8, verbose=False)
        # Limited top schemes.
        self.options['NTOPS'] = Option(
            sw_gbuf_bypass=(False,) * 3, sw_solve_loopblocking=False,
            hw_access_forwarding=False, hw_gbuf_sharing=False,
            partition_hybrid=None, partition_batch=None, partition_ifmaps=None,
            ntops=10, nprocesses=1, verbose=False)
        # Bypass.
        self.options['BYP'] = Option(
            sw_gbuf_bypass=(True,) * 3, sw_solve_loopblocking=False,
            hw_access_forwarding=False, hw_gbuf_sharing=False,
            partition_hybrid=None, partition_batch=None, partition_ifmaps=None,
            ntops=2 ** 30, nprocesses=1, verbose=False)
        # Bypass solver.
        self.options['BYPSOL'] = Option(
            sw_gbuf_bypass=(True,) * 3, sw_solve_loopblocking=True,
            hw_access_forwarding=False, hw_gbuf_sharing=False,
            partition_hybrid=None, partition_batch=None, partition_ifmaps=None,
            ntops=2 ** 30, nprocesses=1, verbose=False)
        # Access forwarding.
        self.options['ACCFWD'] = Option(
            sw_gbuf_bypass=(False,) * 3, sw_solve_loopblocking=False,
            hw_access_forwarding=True, hw_gbuf_sharing=False,
            partition_hybrid=None, partition_batch=None, partition_ifmaps=None,
            ntops=2 ** 30, nprocesses=1, verbose=False)
        # Buffer sharing.
        self.options['BUFSHR'] = Option(
            sw_gbuf_bypass=(False,) * 3, sw_solve_loopblocking=False,
            hw_access_forwarding=False, hw_gbuf_sharing=True,
            partition_hybrid=None, partition_batch=None, partition_ifmaps=None,
            ntops=2 ** 30, nprocesses=1, verbose=False)
        # Buffer sharing with bypassing.
        self.options['BUFSHR-BYP'] = Option(
            sw_gbuf_bypass=(True,) * 3, sw_solve_loopblocking=False,
            hw_access_forwarding=False, hw_gbuf_sharing=True,
            partition_hybrid=None, partition_batch=None, partition_ifmaps=None,
            ntops=2 ** 30, nprocesses=1, verbose=False)

        # Cost.
        self.cost = Cost(mac_op=1, mem_hier=(200, 6, 2, 1),
                         noc_hop=50, unit_static=50)

        # Partition occupation.
        self.part_occ = 0.91


    def _lbs(self, bl_ts, bl_ords=None, wlkey='BASE', rsrckey='BASE',
             optkey='BASE', part_occ=1):
        ''' Make a LoopBlockingScheme instance. '''
        bl_ords = (tuple(range(le.NUM)), tuple(range(le.NUM))) \
                if not bl_ords else bl_ords
        return LoopBlockingScheme(self.nld[wlkey], bl_ts, bl_ords,
                                  self.resource[rsrckey], self.bufshr,
                                  part_occ, self.options[optkey])

    def _gen_loopblocking_all(self, wlkey='BASE'):
        ''' Generate all combinations of loop blocking factors and orders. '''
        for ti, to, tb, orders in itertools.product(
                Util.factorize(self.nld[wlkey].loopcnt[le.IFM], 3),
                Util.factorize(self.nld[wlkey].loopcnt[le.OFM], 3),
                Util.factorize(self.nld[wlkey].loopcnt[le.BAT], 3),
                itertools.product(
                    itertools.permutations(range(le.NUM)),
                    itertools.permutations(range(le.NUM)))):
            lp_ts = [None] * le.NUM
            lp_ts[le.IFM] = ti
            lp_ts[le.OFM] = to
            lp_ts[le.BAT] = tb
            yield tuple(zip(*lp_ts)), orders

    def _make_bl_ts(self, ti_part, to_part, tb_part, wlkey='BASE'):
        '''
        Make a set of blocking factors. `ti_part`, `to_part`, `tb_part` can
        contain one 0 value to be filled.
        '''
        try:
            idx = ti_part.index(0)
        except ValueError:
            ti = ti_part
        else:
            ti = [ti_part[x] if x != idx
                  else Util.idivc(self.nld[wlkey].loopcnt[le.IFM],
                                  Util.prod(ti_part[:idx] + ti_part[idx+1:]))
                  for x in range(3)]
        try:
            idx = to_part.index(0)
        except ValueError:
            to = to_part
        else:
            to = [to_part[x] if x != idx
                  else Util.idivc(self.nld[wlkey].loopcnt[le.OFM],
                                  Util.prod(to_part[:idx] + to_part[idx+1:]))
                  for x in range(3)]
        try:
            idx = tb_part.index(0)
        except ValueError:
            tb = tb_part
        else:
            tb = [tb_part[x] if x != idx
                  else Util.idivc(self.nld[wlkey].loopcnt[le.BAT],
                                  Util.prod(tb_part[:idx] + tb_part[idx+1:]))
                  for x in range(3)]
        lp_ts = [None] * le.NUM
        lp_ts[le.IFM] = ti
        lp_ts[le.OFM] = to
        lp_ts[le.BAT] = tb
        return tuple(zip(*lp_ts))

    def _gen_all_partition(self):
        '''
        Generate PartitionScheme, partitioned NestedLoopDesc, and partition
        occupation.
        '''
        options = Option(
            sw_gbuf_bypass=(False,) * 3, sw_solve_loopblocking=False,
            hw_access_forwarding=False, hw_gbuf_sharing=False,
            partition_hybrid=True, partition_batch=True, partition_ifmaps=True,
            ntops=2 ** 30, nprocesses=1, verbose=False)

        for part in Partition.gen_partition(self.layer['PAR'], self.batch_size,
                                            self.resource['PAR'].dim_nodes,
                                            options):
            p_layer, p_batch_size, p_occ = part.part_layer(self.layer['PAR'],
                                                           self.batch_size)

            p_nld = next(MapStrategyEyeriss(p_layer, p_batch_size,
                                            self.resource['PAR'].dim_array)
                         .gen_nested_loop_desc())

            yield part, p_nld, p_occ

    def _total_part_size(self, part):
        ''' Get the total partitioned data size. '''
        layer = self.layer['PAR']

        nifm = Util.idivc(layer.nifm, part.size(pe.INPP)) * part.size(pe.INPP)
        nofm = Util.idivc(layer.nofm, part.size(pe.OUTP)) * part.size(pe.OUTP)
        hofm = Util.idivc(layer.hofm, part.dim(pe.OFMP).h) * part.dim(pe.OFMP).h
        wofm = Util.idivc(layer.wofm, part.dim(pe.OFMP).w) * part.dim(pe.OFMP).w
        batch_size = Util.idivc(self.batch_size, part.size(pe.BATP)) \
                * part.size(pe.BATP)

        full_layer = ConvLayer(nifm, nofm, (hofm, wofm),
                               layer.sfil,
                               (layer.htrd, layer.wtrd))
        filter_size = full_layer.total_filter_size()
        ifmap_size = full_layer.total_ifmap_size(batch_size)
        ofmap_size = full_layer.total_ofmap_size(batch_size)

        self.assertGreaterEqual(filter_size, layer.total_filter_size())
        self.assertLess(filter_size, layer.total_filter_size() * 1.2 * 1.2)
        self.assertGreaterEqual(ofmap_size,
                                layer.total_ofmap_size(self.batch_size))
        self.assertLess(ofmap_size,
                        layer.total_ofmap_size(self.batch_size)
                        * 1.2 * 1.2 * 1.2)
        self.assertGreaterEqual(ifmap_size,
                                layer.total_ifmap_size(self.batch_size))

        return filter_size, ifmap_size, ofmap_size


    class _SimBuffer(object):
        ''' A data buffer model for simulation. '''

        def __init__(self, buf_cnt_pr, unit_size, is_ofm, bypass=False):

            self.is_ofm = is_ofm
            self.bypass = bypass

            # Accesses to this level, in unit counts (* unit size).
            self.access = 0

            # The size of one unit.
            self.unit_size = unit_size

            if self.bypass:
                return

            # The buffered data range, in the form of the range index, of all
            # dimensions. E.g., (ri0, ri1).
            self.data = (float('nan'), float('nan'))

            # The count of buffered units, aka, range size, of all dimensions.
            # E.g., (c0, c1).
            self.buf_cnt_pr = buf_cnt_pr

        def access_size(self):
            ''' Get access size. '''
            return self.access * self.unit_size

        def do_access(self, idx_pr, cnt_pr, read=1, write=0):
            '''
            Access the buffer by `read` and/or `write`, with the unit index
            `idx_pr` and count `cnt_pr`, of all dimensions.

            Return the count of the accessing data to the next level, of all
            dimensions.
            '''
            if self.bypass:
                # Bypass, relay to the next level.
                return cnt_pr

            # Range index.
            ridx_pr = tuple(idx // buf_cnt for idx, buf_cnt
                            in zip(idx_pr, self.buf_cnt_pr))

            # Access.
            self.access += Util.prod(cnt_pr) * (read + write)

            if ridx_pr == self.data:
                # Hit.
                return (0, 0)

            # Miss.
            self.data = ridx_pr
            return self.buf_cnt_pr

    def _sim_access(self, lbs):
        '''
        Get data access by actually simulating and generating loops.
        '''
        self.assertTrue(lbs.is_valid(), '_sim_access: invalid lbs.')

        lpts = zip(*lbs.bl_ts)

        drams = [None] * de.NUM
        for dce, buf_cnt_pr in zip(
                [de.FIL, de.IFM, de.OFM],
                [(Util.prod(lpts[le.IFM]), Util.prod(lpts[le.OFM])),
                 (Util.prod(lpts[le.IFM]), Util.prod(lpts[le.BAT])),
                 (Util.prod(lpts[le.OFM]), Util.prod(lpts[le.BAT]))]):
            drams[dce] = self._SimBuffer(buf_cnt_pr,
                                         lbs.unit_access[me.DRAM][dce],
                                         is_ofm=(dce == de.OFM)
                                        )
        gbufs = [None] * de.NUM
        for dce, buf_cnt_pr in zip(
                [de.FIL, de.IFM, de.OFM],
                [(Util.prod(lpts[le.IFM][1:]), Util.prod(lpts[le.OFM][1:])),
                 (Util.prod(lpts[le.IFM][1:]), Util.prod(lpts[le.BAT][1:])),
                 (Util.prod(lpts[le.OFM][1:]), Util.prod(lpts[le.BAT][1:]))]):
            gbufs[dce] = self._SimBuffer(buf_cnt_pr,
                                         lbs.unit_access[me.GBUF][dce],
                                         is_ofm=(dce == de.OFM),
                                         bypass=(not lbs.stored_in_gbuf[dce])
                                        )
        regfs = [None] * de.NUM
        for dce, buf_cnt_pr in zip(
                [de.FIL, de.IFM, de.OFM],
                [(Util.prod(lpts[le.IFM][2:]), Util.prod(lpts[le.OFM][2:])),
                 (Util.prod(lpts[le.IFM][2:]), Util.prod(lpts[le.BAT][2:])),
                 (Util.prod(lpts[le.OFM][2:]), Util.prod(lpts[le.BAT][2:]))]):
            regfs[dce] = self._SimBuffer(buf_cnt_pr,
                                         lbs.unit_access[me.REGF][dce],
                                         is_ofm=(dce == de.OFM)
                                        )

        # Already generated psum for OFM.
        ofm_psum = set()

        # Simulation.
        for iidx, oidx, bidx in lbs.gen_index():

            for dce, idx_pr in zip([de.FIL, de.IFM, de.OFM],
                                   [(iidx, oidx), (iidx, bidx), (oidx, bidx)]):
                if dce == de.OFM:
                    # Fetch and writeback, unless for the first time (no fetch).
                    write = 1
                    read = 1 if idx_pr in ofm_psum else 0
                    ofm_psum.add(idx_pr)
                else:
                    read = 1
                    write = 0

                # PE.
                cnt_pr = (1, 1)

                # REGF.
                cnt_pr = regfs[dce].do_access(idx_pr, cnt_pr, read, write)
                if not any(cnt_pr):
                    continue

                # GBUF.
                cnt_pr = gbufs[dce].do_access(idx_pr, cnt_pr, read, write)
                if not any(cnt_pr):
                    continue

                # DRAM.
                cnt_pr = drams[dce].do_access(idx_pr, cnt_pr, read, write)
                if not any(cnt_pr):
                    continue

        dram_access = [drams[dce].access_size() for dce in range(de.NUM)]
        gbuf_access = [gbufs[dce].access_size() for dce in range(de.NUM)]
        return dram_access, gbuf_access


    def _regularized_scheme(self, bl_ts, bl_ords):
        ''' Get the regularized scheme which will not be skipped. '''

        assert isinstance(bl_ts, tuple) and isinstance(bl_ords, tuple)
        assert all(isinstance(t, tuple) for t in bl_ts)
        assert all(isinstance(o, tuple) for o in bl_ords)

        reg_lpts = [[] for _ in range(le.NUM)]
        reg_ords = tuple()

        outer_level_innermost_loop = None

        for t_, ord_ in itertools.izip_longest(bl_ts, bl_ords, fillvalue=None):

            # Non-trivial loops and trivial loops of this level.
            ntlp_list = sorted(lpe for lpe in range(le.NUM)
                               if t_[lpe] > 1)
            trlp_list = sorted(lpe for lpe in range(le.NUM)
                               if lpe not in ntlp_list)

            # Innermost non-trivial loop.
            try:
                ntlp_innermost = min(ntlp_list,
                                     key=lambda lpe, o=ord_: o[lpe])
            except (ValueError, TypeError):
                # All trivial loops or no order (last level).
                assert not ntlp_list or not ord_
                ntlp_innermost = None

            if ord_:
                # Order trivial and non-trivial loops separately of this level.
                reg_ord = [None] * le.NUM
                # Innermost loop.
                try:
                    reg_ord[ntlp_innermost] = 0
                    o = 1
                except TypeError:
                    o = 0
                # First non-trivial loops (inner), then trivial loops (outer).
                for lpe in ntlp_list + trlp_list:
                    if lpe == ntlp_innermost:
                        continue
                    reg_ord[lpe] = o
                    o += 1
                assert o == le.NUM

                # Loop orders.
                reg_ords += (tuple(reg_ord),)

            # Blocking factors.
            for lpe in range(le.NUM):
                reg_lpts[lpe].append(t_[lpe])

            if ntlp_list:
                if outer_level_innermost_loop != ntlp_innermost \
                        and outer_level_innermost_loop in ntlp_list:
                    # Adjust blocking factors by merging two adjacent loops to
                    # the outer one.
                    lpe = outer_level_innermost_loop
                    reg_lpts[lpe][-2] *= reg_lpts[lpe][-1]
                    reg_lpts[lpe][-1] = 1

                outer_level_innermost_loop = ntlp_innermost

        reg_ts = tuple(zip(*reg_lpts))

        if reg_ts == bl_ts and reg_ords == bl_ords:
            return reg_ts, reg_ords

        # Recursive call, since loop merging/reordering may cause further loop
        # merging/reordering.
        return self._regularized_scheme(reg_ts, reg_ords)

