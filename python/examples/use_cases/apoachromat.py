"""Use Case:
     Optimize apoachromatic transport system for plasma wakefield accelerator.
"""


import os
import sys
from dataclasses import dataclass
from typing import ClassVar

import gtpsa

import numpy as np

from thor_scsi.utils import linear_optics as lo, courant_snyder as cs, \
    lattice_properties as lp, index_class as ind
from thor_scsi.utils.output import mat2txt, vec2txt


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


class new():
    def tpsa():
        return gtpsa.tpsa(gtpsa_prop.desc, gtpsa_prop.no)
    def ss_vect_tpsa():
        return gtpsa.ss_vect_tpsa(gtpsa_prop.desc, gtpsa_prop.no)


def compute_Twiss(M):
    n_dof = 2
    eta = np.zeros(2*n_dof)
    alpha = np.zeros(n_dof)
    beta = np.zeros(n_dof)
    nu = np.zeros(n_dof)
    eta = cs.compute_dispersion(M.jacobian()[0:6, 0:6])
    M_mat = M.jacobian()
    for k in range(n_dof):
        tr = np.trace(M_mat[2*k:2*k+2, 2*k:2*k+2])
        nu[k] = np.arccos(tr/2e0)/(2e0*np.pi)
        if M_mat[2*k, 2*k+1] < 0e0:
            nu[k] = 1e0 - nu[k]
        alpha[k] = \
            (M_mat[2*k, 2*k]-np.cos(2e0*np.pi*nu[k]))/np.sin(2e0*np.pi*nu[k])
        beta[k] = M_mat[2*k, 2*k+1]/np.sin(2e0*np.pi*nu[k])
    return eta, alpha, beta, nu


def compute_xi():
    sum = 0e0
        

gtpsa_prop.no = 1
gtpsa_prop.desc = gtpsa.desc(gtpsa_prop.nv, gtpsa_prop.no)

cod_eps = 1e-15
E_0     = 3.0e9

A_max     = np.array([6e-3, 3e-3])
beta_inj  = np.array([3.0, 3.0])
delta_max = 3e-2

home_dir = os.path.join(
    os.environ["HOME"], "Nextcloud", "thor_scsi", "JB", "MAX_IV")
lat_name = sys.argv[1]
file_name = os.path.join(home_dir, lat_name+".lat")

lat_prop = lp.lattice_properties_class(gtpsa_prop, file_name, E_0, cod_eps)

lat_prop.prt_lat("lat_prop_lat.txt")

lat_prop._M = \
    lo.compute_map(
        lat_prop._lattice, lat_prop._model_state, desc=lat_prop._desc)
lat_prop.prt_M()
eta, alpha, beta, nu = compute_Twiss(lat_prop._M)

print(f"\n  eta   = [{eta[ind.x]:10.3e}, {eta[ind.px]:10.3e}]")
print(f"  nu    = [{nu[ind.X]:8.5f},   {nu[ind.Y]:8.5f}]")
print(f"  alpha = [{alpha[ind.X]:10.3e}, {alpha[ind.Y]:10.3e}]")
print(f"  beta  = [{beta[ind.X]:8.5f},   {beta[ind.Y]:8.5f}]")

eta_0 = np.zeros(4)
alpha_0 = np.zeros(2)
beta_0 = np.array([4.31154, 3.92107])
A_0 = lo.compute_A(eta_0, alpha_0, beta_0, lat_prop._desc)
print("\nA_0:\n"+mat2txt(A_0.jacobian()[0:6, 0:6]))
A_1 = new.ss_vect_tpsa()
A_1.compose(lat_prop._M, A_0)
A_1_mat, _ = cs.compute_A_CS(2, A_1.jacobian()[0:6, 0:6])
print("\nA_1:\n"+mat2txt(A_1_mat))

etas, twiss = lo.transform_matrix_extract_twiss(A_1_mat)
print("\n", etas)
print(twiss)
