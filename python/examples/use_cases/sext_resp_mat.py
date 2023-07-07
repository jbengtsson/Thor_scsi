import enum
import logging

# Levels: DEBUG, INFO, WARNING, ERROR, and CRITICAL.
logging.basicConfig(level="WARNING")
logger = logging.getLogger("thor_scsi")

from scipy import optimize

import copy as _copy
from dataclasses import dataclass
import math
import os
from typing import Sequence
from typing import Tuple

import numpy as np
import xarray as xr
import matplotlib.pyplot as plt

import gtpsa
import thor_scsi.lib as tslib

from thor_scsi.utils import knobs
from thor_scsi.factory import accelerator_from_config
from thor_scsi.utils.accelerator import instrument_with_standard_observers
from thor_scsi.utils.twiss_output import twiss_ds_to_df, df_to_tsv

from thor_scsi.utils.extract_info import accelerator_info
from thor_scsi.utils import linear_optics as lo, courant_snyder as cs

# from thor_scsi.utils.phase_space_vector import map2numpy
from thor_scsi.utils.output import prt2txt, mat2txt, vec2txt

named_index_d = dict(x=0, px=1, y=2, py=3, delta=4, ct=5, K=6, dx=7, dy=8)
named_index = gtpsa.IndexMapping(named_index_d)

# Variables max order.
mo = 2
# Parameters max order.
po = 1

# Descriptor for Truncated Power Series Algebra variables.
desc = gtpsa.desc(6, mo, 3, po)

# Configuration space coordinates.
X_, Y_, Z_ = [
    tslib.spatial_index.X,
    tslib.spatial_index.Y,
    tslib.spatial_index.Z
]
# Phase-space coordinates.
[x_, px_, y_, py_, ct_, delta_] = [
    tslib.phase_space_index_internal.x,
    tslib.phase_space_index_internal.px,
    tslib.phase_space_index_internal.y,
    tslib.phase_space_index_internal.py,
    tslib.phase_space_index_internal.ct,
    tslib.phase_space_index_internal.delta,
]


class MultipoleIndex(enum.IntEnum):
    quadrupole = 2
    sextupole = 3


def prt_Twiss(str, Twiss):
    """

    todo:
        rename str e.g. header? prefix?

    """
    # eta, alpha, beta = Twiss[0], Twiss[1], Twiss[2]
    # that way I also check that Twiss has exactly three parameters
    eta, alpha, beta = Twiss
    print(str, end="")
    print(f"  eta    = [{eta[X_]:9.3e}, {eta[Y_]:9.3e}]")
    print(f"  alpha  = [{alpha[X_]:9.3e}, {alpha[Y_]:9.3e}]")
    print(f"  beta   = [{beta[X_]:5.3f}, {beta[Y_]:5.3f}]")


def compute_periodic_solution(lat, model_state):
    """
    Todo:
        model_state: rename to calculation_configuration or calc_config
    """
    # Compute the periodic solution for a super period.
    # Degrees of freedom - RF cavity is off; i.e., coasting beam.
    n_dof = 2
    model_state.radiation = False
    model_state.Cavity_on = False

    stable, M, A = lo.compute_map_and_diag(n_dof, lat, model_state, desc=desc,
                                           tpsa_order=mo)
    print("\nM:\n", M)
    res = cs.compute_Twiss_A(A)
    Twiss = res[:3]
    prt_Twiss("\nTwiss:\n", Twiss)
    A_map = gtpsa.ss_vect_tpsa(desc, 1)
    A_map.set_jacobian(A)
    ds = \
        lo.compute_Twiss_along_lattice \
        (n_dof, lat, model_state, A=A_map, desc=desc, mapping=named_index)

    return M, A, ds


def prt_map(str, map):
    print(str)
    map.x.print()
    map.px.print()
    map.y.print()
    map.py.print()
    map.delta.print()
    map.ct.print()


t_dir = os.path.join(os.environ["HOME"], "Nextcloud", "thor_scsi", "JB")
t_file = os.path.join(t_dir, "b3_sfsf4Q_tracy_jb_3.lat")

# Read in & parse lattice file.
lat = accelerator_from_config(t_file)
lat_tpsa = accelerator_from_config(t_file)

# Set lattice state (Rf cavity on/off, etc.)
model_state = tslib.ConfigType()

n_dof = 2
model_state.radiation = False
model_state.Cavity_on = False

M, A, data = compute_periodic_solution(lat, model_state)

elem = lat_tpsa.find("uq4", 0)
print("\nuq4:\n", elem)

elem = knobs.convert_magnet_to_knobbable(elem)
knobs.make_magnet_knobbable(
    elem, po=po, desc=desc, named_index=named_index, offset=True)
print("\nuq4:\n", elem)

M = gtpsa.ss_vect_tpsa(desc, mo, 6, index_mapping=named_index)
M.set_identity()
lat_tpsa.propagate(model_state, M)
print("\nM:\n", M)

if not False:
    prt_map("\nM:", M)
