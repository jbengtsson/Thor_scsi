"""Use Case:
     Compute the orbit shift from reverse bends.
"""

import logging

# Levels: DEBUG, INFO, WARNING, ERROR, and CRITICAL.
logging.basicConfig(level="ERROR")
logger = logging.getLogger("thor_scsi")

import os
import sys
from dataclasses import dataclass
from typing import ClassVar

import math
import numpy as np

import gtpsa

import thor_scsi.lib as ts

from thor_scsi.utils import lattice_properties as lp, nonlin_dyn as nld_cl, \
    closed_orbit as co, index_class as ind


ind = ind.index_class()


@dataclass
class gtpsa_prop:
    # GTPSA properties.
    # Number of variables - phase-space coordinates & 1 for parameter
    #dependence.
    nv: ClassVar[int] = 6 + 1
    # Max order.
    no: ClassVar[int] = 1
    # Number of parameters.
    nv_prm: ClassVar[int] = 0
    # Parameters max order.
    no_prm: ClassVar[int] = 0
    # Index.
    named_index = gtpsa.IndexMapping(dict(x=0, px=1, y=2, py=3, delta=4, ct=5))
    # Descriptor
    desc : ClassVar[gtpsa.desc]


def compute_optics(lat_prop):
    try:
        # Compute Twiss parameters along lattice.
        if not lat_prop.comp_per_sol():
            print("\ncomp_per_sol: unstable")
            raise ValueError

        # Compute radiation properties.
        stable, stable_rad = lat_prop.compute_radiation()
        print(stable, stable_rad)
        if not stable:
            print("\ncompute_radiation: unstable")
            raise ValueError
    except ValueError:
        assert False


def get_lat(home_dir, lat_name, E_0):
    file_name = os.path.join(home_dir, lat_name+".lat")

    lat_prop = lp.lattice_properties_class(gtpsa_prop, file_name, E_0, cod_eps)
    lat_prop.prt_lat(lat_name+"_lat.txt")

    print("\n{:s}".format(lat_name))
    print("Circumference [m]      = {:7.5f}".format(lat_prop.compute_circ()))
    print("Total bend angle [deg] = {:7.5f}".format(lat_prop.compute_phi_lat()))

    lat_prop.prt_lat(lat_name+"_lat.txt")

    # Computes element s location: lat_prop._Twiss.s[].
    compute_optics(lat_prop)
    lat_prop._model_state.radiation = False

    if False:
        lat_prop.prt_lat_param()
        lat_prop.prt_rad()
        lat_prop.prt_M()
        lat_prop.prt_M_rad()

    if False:
        lat_prop.plt_Twiss("compute_orbit_Twiss.png", not False)

    return lat_prop


def prt_bend(lat_ref, lat_prop):
    file_name = "prt_bend.txt"
    file = open(file_name, "w")

    phi_tot_ref = 0e0
    phi_tot = 0e0
    print("#  k      s        name                  L              phi"
          "         b_1xL   b_1xL_sum\n"
          "#        [m]                            [m]            [deg]"
          "        [mrad]    [mrad]", file=file)
    b_1xL_sum = 0e0
    for k in range(len(lat_ref._lattice)):
        if (type(lat_prop._lattice[k]) == ts.Bending) or \
           (type(lat_prop._lattice[k]) == ts.Quadrupole):
            b = lat_prop._lattice[k]
            h = b.get_curvature()
            if h != 0e0:
                b_ref = lat_ref._lattice[k]
                fam_name_ref = b_ref.name
                index_ref = b_ref.index
                s = lat_ref._Twiss.s[index_ref]
                L_ref = b_ref.get_length()
                phi_ref = math.degrees(L_ref*b_ref.get_curvature())
                phi_tot_ref += phi_ref

                fam_name = b.name
                L = b.get_length()
                phi = math.degrees(L*h)
                phi_tot += phi

                b_1xL = math.radians(phi-phi_ref)
                b_1xL_sum += b_1xL
                b.get_multipoles().set_multipole(1, b_1xL/L)

                print("  {:3d}  {:6.3f}  {:8s} ({:8s})  {:5.3f} ({:5.3f})" \
                      "  {:6.3f} ({:6.3f})  {:6.3f}   {:6.3f}".
                      format(index_ref, s, fam_name_ref, fam_name, L_ref, L,
                             phi_ref, phi, 1e3*b_1xL, 1e3*b_1xL_sum), file=file)
    print("\n  phi_tot = {:8.5f} ({:8.5f})".format(phi_tot_ref, phi_tot),
        file=file)
    file.close()


def prt_orbit(lat_prop):
    file_name = "prt_orbit.txt"
    file = open(file_name, "w")

    # r = co.compute_closed_orbit(
    #     lat_prop._lattice, lat_prop._model_state, delta=0e0, max_iter=10,
    #     eps=1e-10, desc=lat_prop._desc)

    M = gtpsa.ss_vect_tpsa(lat_prop._desc, 1)
    M.set_identity()
    # M.px += -0.448e-3
    # M += r.x0
    print("# k               s    type     x       p_x\n"
          "#                [m]           [mm]    [mrad]", file=file)
    for k in range(len(lat_prop._lattice)):
        lat_prop._lattice.propagate(lat_prop._model_state, M, k, 1)
        s = lat_ref._Twiss.s[k]
        print("{:3d}  {:8s}  {:6.3f}  {:4.1f}  {:7.3f}  {:7.3f}".format(
            k, lat_prop._lattice[k].name, s, lat_prop._type_code[k],
            1e3*M.cst().x, 1e3*M.cst().px), file=file)


# TPSA max order.
gtpsa_prop.no = 2

cod_eps = 1e-15
E_0     = 3.0e9

A_max     = np.array([6e-3, 3e-3])
delta_max = 3e-2
beta_inj  = np.array([3.0, 3.0])

home_dir = os.path.join(
    os.environ["HOME"], "Nextcloud", "thor_scsi", "JB", "MAX_IV")
home_dir_1 = os.path.join(home_dir, "max_iv")
home_dir_2 = os.path.join(home_dir, "max_4u")
lat_ref = get_lat(home_dir_1, "max_iv_baseline", E_0)
lat_prop = get_lat(home_dir_2, "max_4u_sp_jb_5", E_0)

prt_bend(lat_ref, lat_prop)

b_n_list = ["q1", "q2", "q3", "s1", "s2", "s3", "s4", "o1", "o2", "o3"]
nld = nld_cl.nonlin_dyn_class(lat_prop, A_max, beta_inj, delta_max, b_n_list)
nld.zero_mult(lat_prop, 2)
nld.zero_mult(lat_prop, 3)
nld.zero_mult(lat_prop, 4)

prt_orbit(lat_prop)
