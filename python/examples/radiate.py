"""Read lattice file and calculate radiation
"""
import logging
import xarray as xr

#logging.basicConfig(level="DEBUG")

from thor_scsi.factory import accelerator_from_config
from thor_scsi.lib import (
    ConfigType,
    ss_vect_tps,
    ss_vect_double,
    RadiationDelegate,
    RadiationDelegateKick,
    ObservedState
)
from thor_scsi.lib import phase_space_index_internal as phase_space_ind

logging.basicConfig(level="DEBUG")
from thor_scsi.factory import accelerator_from_config
from thor_scsi.utils.accelerator import instrument_with_radiators
from thor_scsi.utils.radiate import calculate_radiation
import os

import numpy as np
import scipy as sp

import thor_scsi.lib as tslib

# from thor_scsi.utils.linalg import match_eigenvalues_to_plane_orig
from thor_scsi.utils.closed_orbit import compute_closed_orbit
from thor_scsi.utils.output import vec2txt, mat2txt
from thor_scsi.utils.linear_optics import compute_dispersion, compute_A_CS
from thor_scsi.utils.linalg import compute_A_prev, omega_block_matrix


X_ = 0
Y_ = 1
Z_ = 2


def chop_vec(vec, eps):
    for k in range(vec.size):
        if np.abs(vec[k]) < eps:
            vec[k] = 0e0
    return vec


def chop_mat(mat, eps):
    for k in range(mat[:, 0].size):
        chop_vec(mat[k, :], eps)
    return mat


def chop_cmplx_vec(vec, eps):
    for k in range(vec.size):
        [x, y] = [vec[k].real, vec[k].imag]
        if np.abs(x) < eps:
            x = 0e0
        if np.abs(y) < eps:
            y = 0e0
        vec[k] = complex(x, y)
    return vec


def chop_cmplx_mat(mat, eps):
    for k in range(mat[:, 0].size):
        chop_cmplx_vec(mat[k, :], eps)
    return mat


def acos2(sin, cos):
    # Calculate the normalised phase advance from the Poincaré map:
    #   Tr{M} = 2 cos(2 pi nu)
    # i.e., assuming mid-plane symmetry.
    # The sin part is used to determine the quadrant.
    mu = np.arccos(cos)
    if sin < 0e0:
        mu = 2e0*np.pi - mu
    return mu


def calculate_nu(M):
    tr = M.trace()
    # Check if stable.
    if tr < 2e0:
        calculate_nu(tr/2e0,  M[0][1])/(2e0*np.pi)
        return nu
    else:
        print("\ncalculate_nu: unstable\n")
        return float('nan')


def calculate_nus(n_dof, M):
    nus = np.zeros(n_dof, float)
    for k in range(n_dof):
        nus[k] = calculate_nu(M[2*k:2*k+2, 2*k:2*k+2])/(2e0*np.pi)
        if n_dof == 3:
            nus[2] = 1e0 - nus[2]
    return nus


def calculate_nu_symp(n_dof, M):
    # Calculate normalised phase advance from a symplectic periodic matrix.
    n = 2*dof
    I = np.identity(4)
    tr = np.zeros(n_dof, float)
    for k in range(n_dof):
        tr[k] = np.trace(M[2*k:2*k+2, 2*k:2*k+2])
    M4b4 = M[0:4, 0:4]
    [p1, pm1] = [np.linalg.det(M4b4-I), np.linalg.det(M4b4+I)]
    [po2, q] = [(p1-pm1)/16e0, (p1+pm1)/8e0 - 1e0]
    if tr[X_] > tr[Y_]:
        sgn = 1
    else:
        sgn = -1
    [x, y] = [-po2+sgn*np.sqrt(po2**2-q), -po2-sgn*np.sqrt(po2**2-q)]
    nu = []
    nu.extend([acos2(M[0][1], x)/(2e0*np.pi), acos2(M[2][3], y)/(2e0*np.pi)])
    if n_dof == 3:
        nu.append(1e0-acos2(M[4][5], tr[Z_]/2e0)/(2e0*np.pi))
    return np.array(nu)


def find_closest_nu(nu, w):
    min = 1e30
    for k in range(w.size):
        nu_k = acos2(w[k].imag, w[k].real)/(2e0*np.pi)
        diff =  np.abs(nu_k-nu)
        if diff < min:
            [ind, min] = [k, diff]
    return ind


def sort_eigen_vec(dof, nu, w):
    order = np.zeros(2*dof, int)
    for k in range(dof):
        order[2*k]   = find_closest_nu(nu[k], w)
        order[2*k+1] = find_closest_nu(1e0-nu[k], w)
    return order


t_dir = os.path.join(os.environ["HOME"], "Nextcloud", "thor_scsi")
#t_file = os.path.join(t_dir, "b3_tst.lat")
t_file = os.path.join(t_dir, "b3_sf_40Grad_JB.lat")

acc = accelerator_from_config(t_file)
print(" ".join([elem.name for elem in acc]))
print("Length", np.sum([elem.getLength() for elem in acc]))

# b2 = acc.find("b2", 0)

# energy = 2.5e9

# cav.setVoltage(cav.getVoltage() * 1./2.)
# cav.setVoltage(0)
cav = acc.find("cav", 0)
print("acc cavity", repr(cav))
txt=\
    f"""Cavity info
frequency         {cav.getFrequency()/1e6} MHz",
voltage           {cav.getVoltage()/1e6} MV
harmonic number   {cav.getHarmonicNumber()}
    """
print(txt)

# cav.setVoltage(cav.getVoltage() * 1./2.)
# cav.setVoltage(0)
cav = acc.find("cav", 0)
print("acc cavity", repr(cav))
txt=\
    f"""Cavity info
frequency         {cav.getFrequency()/1e6} MHz",
voltage           {cav.getVoltage()/1e6} MV
harmonic number   {cav.getHarmonicNumber()}
    """
print(txt)

radiate = not True
calc_config = tslib.ConfigType()
calc_config.radiation = radiate
# is this used anywhere?
calc_config.emittance = False
calc_config.Cavity_on = not True

print(
    "calc_config",
    calc_config.radiation,
    calc_config.emittance,
    calc_config.Cavity_on,
)

debug_prt = not False

calc_config.Energy = 2.5e9

if calc_config.Cavity_on == True:
    dof = 3
else:
    dof = 2
n = 2 * dof

r = compute_closed_orbit(acc, calc_config, delta=0e0)
M = r.one_turn_map[:6, :6]
print("\nM:\n"+mat2txt(M))

nu_symp = calculate_nu_symp(dof, M)
# Diagonalise M.
[w, u] = np.linalg.eig(M[:n, :n])

nu_eig = np.zeros(n)
for k in range(n):
    nu_eig[k] = acos2(w[k].imag, w[k].real)/(2e0*np.pi)

if debug_prt:
    print("\nu:\n"+mat2txt(u))
    print("\nnu_symp:\n"+vec2txt(nu_symp))
    print("\nnu_eig:\n"+vec2txt(nu_eig))
    print("\nlambda:\n"+vec2txt(w))
    # print("\nu:\n"+mat2txt(u))

order = sort_eigen_vec(dof, nu_symp, w)

w_ord = np.zeros(n, complex)
u_ord = np.zeros((n, n), complex)
nu_eig_ord = np.zeros(n, float)
for k in range(n):
    w_ord[k] = w[order[k]]
    u_ord[:, k] = u[:, order[k]]
    nu_eig_ord[k] = acos2(w_ord[k].imag, w_ord[k].real)/(2e0*np.pi)

if debug_prt:
    print("\norder:\n", order)
    print("\nnu_eig_ord:\n"+vec2txt(nu_eig_ord))
    print("\nlambda_ord:\n"+vec2txt(w_ord))
    # print("\nu_ord:\n"+mat2txt(u_ord))
    print("\nu_ord^-1.M.u_ord:\n"+mat2txt(
        chop_cmplx_mat(np.linalg.inv(u_ord) @ M[:n, :n] @ u_ord, 1e-15)))

eta = compute_dispersion(M)

if debug_prt:
    print("\neta:\n", eta)

[A, u1] = compute_A_prev(dof, eta, u_ord)
A_inv = np.linalg.inv(A)

if debug_prt:
    print("\nu1:\n"+mat2txt(u1))
    print("\nu1^-1.M.u1:\n"+mat2txt(
        chop_cmplx_mat(np.linalg.inv(u1) @ M[:n, :n] @ u1, 1e-13)))
    print("\nu1^T.omega.u1:\n"+mat2txt(
        chop_cmplx_mat(u1.T @ omega_block_matrix(dof) @ u1, 1e-13)))
    print("\nA:\n"+mat2txt(chop_mat(A_inv, 1e-13)))
    print("\nA^T.omega.A:\n"+mat2txt(chop_mat(
        A[:n, :n].T @ omega_block_matrix(dof) @ A[:n, :n], 1e-13)))

print("\nA_CS:\n"+mat2txt(chop_mat(compute_A_CS(dof, A)[0], 1e-10)))
print("\nR:\n"+mat2txt(chop_mat(A_inv @ M @ A, 1e-10)))

exit()

r = calculate_radiation(
    acc, energy=2.5e9, calc_config=calc_config, install_radiators=True
)

exit()

use_tpsa = True
if not use_tpsa:
    ps = ss_vect_double()
    ps.set_zero()
    ps[phase_space_ind.x_] = 1e-3
else:
    ps = ss_vect_tps()
    ps.set_identity()


# First step:
#
# use closed orbit
# 1. calculate fix point and Poincarè Map M with damped system (i.e. radiation on
#    and cavity on (without dispersion in a second case)
# 2. diagonalise M = A $\Gamma$ A$^{-1}$
# 3. eigenvalues:
#        - complex part: tunes,
#        - real part: damping times  (refer equation)
#    use eigen values of symplectic matrix to identify the planes
# 4. propagate A, thin kick will create diffusion coeffs (don't forget to zero
#    them before calculation starts (sum it up afterwards


print(ps)
acc.propagate(calc_config, ps, 0, 2000)
print(ps)


if use_tpsa:
    # Inspect curly_H in
    for a_del in rad_del:
        name = a_del.getDelegatorName()
        idx = a_del.getDelegatorIndex()
        curly_H_x = a_del.getCurlydHx()
        txt = f"{name:10s} {idx:4d} curly_H_x {curly_H_x:5f}"
        print(txt)

    I = np.array([a_del.getSynchrotronIntegralsIncrements() for a_del in rad_del_kick])

    for a_del in rad_del_kick:
        name = a_del.getDelegatorName()
        idx = a_del.getDelegatorIndex()
        curly_H_x = a_del.getCurlydHx()
        dI = a_del.getSynchrotronIntegralsIncrements()
        D_rad = a_del.getDiffusionCoefficientsIncrements()

        txt = f"{name:10s} {idx:4d} curly_H_x {curly_H_x: 10.6e}"
        txt += "    dI " + ",".join(["{: 10.6e}".format(v) for v in dI])
        txt += "   "
        txt += "    D_rad" + ",".join(["{: 10.6e}".format(v) for v in D_rad])
        txt += "   "
        print(txt)
