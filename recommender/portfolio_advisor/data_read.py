import os
from dataclasses import dataclass

from tqdm import tqdm

from infra_structure.data_end.kpattern import BarSeries
from infra_structure.data_end.kpattern import BarSeries
from infra_structure.data_engine.visitor.file_visitor import FileVisitor
from research.hig_low_peak.zig_zag import pivots_to_columns
from research.hig_low_peak.zig_zag.zig_zag import plot_zigzag_single, zigzag
from research.hig_low_peak.zig_zag.zig_zag_atr import zigzag_atr
from research.plot_k_direct import plot_k_line

file_visitor = FileVisitor("basic", "stock", "market", "d1", "time_series").data_set()

df_1 = file_visitor.random_one()
df_2 = file_visitor.random_one()
df_3 = file_visitor.random_one()
df_4 = file_visitor.random_one()
df_5 = file_visitor.random_one()
df_6 = file_visitor.random_one()
df_7 = file_visitor.random_one()


