"""Use Case:
     Implementation and general optimisation of a higher-order-achromat.
     Use one unit cell.
"""


import os
import sys
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from scipy import optimize as opt

from thor_scsi.utils import lattice_properties as lp, index_class as ind, \
    linear_optics as lo, prm_class as pc, nonlin_dyn as nld_cl
from thor_scsi.utils.output import mat2txt, vec2txt

import gtpsa


ind = ind.index_class()

phi_max      = 0.85
b_2_bend_max = 1.0
b_2_max      = 10.0

eps_x_des    = 49e-12
alpha_c_des  = 5e-6
nu_uc_des    = [0.4, 0.1]
nu_sp_des    = [2.89, 0.91]
beta_des     = [5.0, 3.0]
dnu_des      = [0.5, 0.25]     # Phase advance across the straight.


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


class opt_sp_class:
    # Private

    def __init__(
            self, lat_prop, prm_list, dprm_list, uc_list, sp_list, weight,
            d1_bend, d2_bend, rb, eps_x_des, nu_uc_des, nu_sp_des,
            beta_des, dnu_des, nld):

        self._lat_prop       = lat_prop
        self._nld            = nld
        self._prm_list       = prm_list
        self._uc_list        = uc_list
        self._sp_list        = sp_list
        self._weight         = weight
        self._d1_bend        = d1_bend
        self._d2_bend        = d2_bend
        self._rb             = rb
        self._eps_x_des      = eps_x_des
        self._nu_uc_des      = nu_uc_des
        self._nu_sp_des      = nu_sp_des
        self._beta_des       = beta_des
        self._dnu_des        = dnu_des

        self._Twiss_sp       = np.nan
        self._eta_list       = np.zeros((2, 4))
        self._alpha_list     = np.zeros((2, 2))
        self._nu_uc          = np.nan
        self._dnu            = np.nan
        self._xi             = np.nan

        self._chi_2_min      = 1e30
        self._n_iter         = -1
        self._file_name      = "opt_sp.txt"

        self._h_im_scl_rms_0 = np.nan
        self._h_im_scl_rms_1 = np.nan
        self._K_re_scl_rms_0 = np.nan
        self._K_re_scl_rms_1 = np.nan

    # Public.

    def compute_phi_bend(self, bend_list):
        phi = 0e0
        for k in range(len(bend_list)):
            phi += self._lat_prop.get_phi_elem(bend_list[k], 0)
        return phi

    def prt_iter(self, prm, chi_2):
        eta, alpha, beta, nu_sp = self._Twiss_sp
        phi = self._lat_prop.compute_phi_lat()
        phi_d1 = self.compute_phi_bend(self._d1_bend._bend_list)
        phi_d2 = self.compute_phi_bend(self._d2_bend._bend_list)
        phi_rb = self._lat_prop.get_phi_elem(self._rb, 0)

        print("\n{:3d} chi_2 = {:9.3e} ({:9.3e})".format(
            self._n_iter, self._chi_2_min, chi_2-self._chi_2_min))
        print("    eps_x [pm.rad] = {:5.3f} [{:5.3f}]".
              format(1e12*self._lat_prop._eps[ind.X], 1e12*self._eps_x_des))

        print("\n    alpha_c        = {:9.3e}".format(self._lat_prop._alpha_c))
        print("    nu_uc          = [{:7.5f}, {:7.5f}] ([{:7.5f}, {:7.5f}])".
              format(self._nu_uc[ind.X], self._nu_uc[ind.Y],
                     self._nu_uc_des[ind.X], self._nu_uc_des[ind.Y]))
        print("    nu_sp          = [{:7.5f}, {:7.5f}] ([{:7.5f}, {:7.5f}])".
              format(nu_sp[ind.X], nu_sp[ind.Y], nu_sp_des[ind.X],
                     nu_sp_des[ind.Y]))
        print("    dnu            = [{:7.5f}, {:7.5f}] ([{:7.5f}, {:7.5f}])".
              format(self._dnu[ind.X], self._dnu[ind.Y],
                     self._dnu_des[ind.X], dnu_des[ind.Y]))
        print("    xi             = [{:5.3f}, {:5.3f}]".
              format(self._xi[ind.X], self._xi[ind.Y]))

        if len(uc_list) == 2:
            print("\n    eta'_uc        = {:9.3e}".
                  format(self._eta_list[0][ind.px]))
            print("    alpha_uc       = [{:9.3e}, {:9.3e}]".
                  format(self._alpha_list[0][ind.X],
                         self._alpha_list[0][ind.Y]))
        else:
            print("\n    eta'_uc        = {:9.3e} {:9.3e}".
                  format(self._eta_list[0][ind.px], self._eta_list[1][ind.px]))
            print("    alpha_uc       = [{:9.3e}, {:9.3e}] [{:9.3e}, {:9.3e}]".
                  format(self._alpha_list[0][ind.X], self._alpha_list[0][ind.Y],
                         self._alpha_list[1][ind.X], self._alpha_list[1][ind.Y]
                         ))
        print("    eta_x          = {:9.3e}".format(eta[ind.x]))
        print("    beta           = [{:7.5f}, {:7.5f}] ([{:7.5f}, {:7.5f}])".
              format(beta[ind.X], beta[ind.Y], self._beta_des[ind.X],
                    self._beta_des[ind.Y]))

        print("\n    phi_sp         = {:8.5f}".format(phi))
        print("    C [m]          = {:8.5f}".
              format(self._lat_prop.compute_circ()))

        print("\n    phi_d1         = {:8.5f}".format(phi_d1))
        print("    phi_d2         = {:8.5f}".format(phi_d2))
        print("    phi_rb         = {:8.5f}".format(phi_rb))

        self._lat_prop.prt_rad()
        print("\n  h_im_scl_rms = {:9.3e} ({:9.3e} <- {:9.3e})".
              format(self._nld._h_im_scl_rms, self._h_im_scl_rms_1,
                     self._h_im_scl_rms_0))
        print("  K_re_scl_rms = {:9.3e} ({:9.3e} <- {:9.3e})".
              format(self._nld._K_re_scl_rms, self._K_re_scl_rms_1,
                     self._K_re_scl_rms_0))
        self._nld.prt_nl(self._lat_prop)

        self._prm_list.prt_prm(prm)

    def compute_chi_2(self):
        prt = not False

        eta, alpha, nu_sp, beta = self._Twiss_sp

        dchi_2 = weight[0]*(self._lat_prop._eps[ind.X]-self._eps_x_des)**2
        chi_2 = dchi_2
        if prt:
            print("\n  dchi2(eps_x)        = {:9.3e}".format(dchi_2))

        dchi_2 = weight[1]*(self._lat_prop._alpha_c-alpha_c_des)**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(alpha_c)      = {:9.3e}".format(dchi_2))

        dchi_2 = weight[2]*self._lat_prop._U_0**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(U_0)          = {:9.3e}".format(dchi_2))

        dchi_2 = weight[3]*(self._eta_list[0][ind.px]**2
                            +self._eta_list[1][ind.px]**2)
        chi_2 += dchi_2
        if prt:
            print("  dchi2(eta'_uc)      = {:9.3e}".format(dchi_2))

        dchi_2 = weight[4]*(
            self._alpha_list[0][ind.X]**2+self._alpha_list[0][ind.Y]**2)
        chi_2 += dchi_2
        if prt:
            print("  dchi2(alpha_uc)     = {:9.3e}".format(dchi_2))

        dchi_2 = weight[4]*(
            self._alpha_list[1][ind.X]**2+self._alpha_list[1][ind.Y]**2)
        chi_2 += dchi_2
        if prt:
            print("  dchi2(alpha_uc)     = {:9.3e}".format(dchi_2))

        dchi_2 = weight[5]*(self._nu_uc[ind.X]-self._nu_uc_des[ind.X])**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(nu_uc_x)      = {:9.3e}".format(dchi_2))

        dchi_2 = weight[6]*(self._nu_uc[ind.Y]-self._nu_uc_des[ind.Y])**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(nu_uc_y)      = {:9.3e}".format(dchi_2))

        dchi_2 = weight[7]*eta[ind.x]**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(eta_x)        = {:9.3e}".format(dchi_2))

        dchi_2 = weight[8]*(nu_sp[ind.X]-self._nu_sp_des[ind.X])**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(nu_sp_x)      = {:9.3e}".format(dchi_2))

        dchi_2 = weight[9]*(nu_sp[ind.Y]-self._nu_sp_des[ind.Y])**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(nu_sp_y)      = {:9.3e}".format(dchi_2))

        dchi_2 = weight[10]*(beta[ind.X]-self._beta_des[ind.X])**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(beta_x)       = {:9.3e}".format(dchi_2))

        dchi_2 = weight[11]*(beta[ind.Y]-self._beta_des[ind.Y])**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(beta_y)       = {:9.3e}".format(dchi_2))

        dchi_2 = weight[12]*(self._dnu[ind.X]-self._dnu_des[ind.X])**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(dnu_x)        = {:9.3e}".format(dchi_2))

        dchi_2 = weight[13]*(self._dnu[ind.Y]-self._dnu_des[ind.Y])**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(dnu_y)        = {:9.3e}".format(dchi_2))

        dchi_2 = weight[14]*(self._xi[ind.X]**2+self._xi[ind.Y]**2)
        chi_2 += dchi_2
        if prt:
            print("  dchi2(xi)           = {:9.3e}".format(dchi_2))

        dchi_2 = weight[15]*self._nld._h_im_scl_rms**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(h_im_scl_rms) = {:9.3e}".format(dchi_2))

        dchi_2 = weight[16]*self._nld._K_re_scl_rms**2
        chi_2 += dchi_2
        if prt:
            print("  dchi2(K_re_scl_rms) = {:9.3e}".format(dchi_2))

        return chi_2

    def opt_sp(self):
        """Use Case: optimise super period.
        """

        def f_sp(prm):
            self._n_iter += 1
            self._prm_list.set_prm(prm)
            if d1_bend != []:
                self._d1_bend.correct_bend_phi()
            if d2_bend != []:
                self._d2_bend.correct_bend_phi()

            try:
                # Compute Twiss parameters along the lattice.
                if not self._lat_prop.comp_per_sol():
                    print("\ncomp_per_sol: unstable")
                    raise ValueError

                # Compute radiation properties.
                stable, stable_rad = self._lat_prop.compute_radiation()
                if not stable or not stable_rad:
                    print("\ncompute_radiation: unstable")
                    raise ValueError
            except ValueError:
                chi_2 = 1e30
                if not False:
                    print("\n{:3d} chi_2 = {:11.5e} ({:11.5e})".
                          format(self._n_iter, chi_2, self._chi_2_min))
                    self._prm_list.prt_prm(prm)
            else:
                _, _, _, self._nu_0 = self._lat_prop.get_Twiss(uc_list[0]-1)
                self._eta_list[0], self._alpha_list[0], _, self._nu_1 = \
                    self._lat_prop.get_Twiss(uc_list[1])
                self._nu_uc = self._nu_1 - self._nu_0
                if len(uc_list) == 3:
                    self._eta_list[1], self._alpha_list[1], _, _ = \
                        self._lat_prop.get_Twiss(self._uc_list[2])
                self._Twiss_sp = self._lat_prop.get_Twiss(-1)
                self._dnu = \
                    self._lat_prop.get_Twiss(-1)[3][:] \
                    - self._lat_prop.get_Twiss(sp_list[1])[3][:] \
                    + self._lat_prop.get_Twiss(sp_list[0])[3][:]

                self._nld.compute_map(self._lat_prop, self._lat_prop._no)
                self._nld.compute_nl(self._lat_prop)
                self._xi =  \
                    np.array(
                        [-self._nld._K_re.get([1, 1, 0, 0, 1, 0, 0])/np.pi,
                         -self._nld._K_re.get([0, 0, 1, 1, 1, 0, 0])/np.pi])

                chi_2 = self.compute_chi_2()

                if chi_2 < self._chi_2_min:
                    self.prt_iter(prm, chi_2)
                    if False:
                        self._lat_prop.prt_Twiss("twiss.txt")
                    pc.prt_lat(
                        self._lat_prop, self._file_name, self._prm_list,
                        d1_bend=self._d1_bend)
                    self._chi_2_min = min(chi_2, self._chi_2_min)
                    self._h_im_scl_rms_1 = self._nld._h_im_scl_rms
                    self._K_re_scl_rms_1 = self._nld._K_re_scl_rms
                else:
                    if False:
                        print("\n{:3d} dchi_2 = {:9.3e}".
                              format(self._n_iter, chi_2-self._chi_2_min))
                        # self._prm_list.prt_prm(prm)

            return chi_2

        max_iter = 1000
        f_tol    = 1e-10
        g_tol    = 1e-7
        x_tol    = 1e-7

        self._nld.compute_map(self._lat_prop, self._lat_prop._no)
        self._nld.compute_nl(self._lat_prop)
        self._h_im_scl_rms_1 = self._h_im_scl_rms_0 = self._nld._h_im_scl_rms
        self._K_re_scl_rms_1 = self._K_re_scl_rms_0 = self._nld._K_re_scl_rms

        prm, bounds = self._prm_list.get_prm()
        f_sp(prm)

        # Methods:
        #   Nelder-Mead, Powell, CG, BFGS, Newton-CG, L-BFGS-B, TNC, COBYLA,
        #   SLSQP, trust-constr, dogleg, truct-ncg, trust-exact, trust-krylov.

        if True:
            # Powell ftol, xtol
            minimum = opt.minimize(
                f_sp,
                prm,
                method="Powell",
                # callback=prt_iter,
                # bounds = bounds,
                options={"ftol": f_tol, "xtol": x_tol, "maxiter": max_iter}
            )
        else:
            # CG     gtol
            minimum = opt.minimize(
                f_sp,
                prm,
                method="CG",
                # callback=prt_iter,
                jac=None,
                options={"gtol": g_tol, "maxiter": max_iter,
                         "eps": dprm_list}
            )

        print("\n".join(minimum))


# TPSA max order.
gtpsa_prop.no = 6

cod_eps = 1e-10
E_0     = 3.0e9

A_max     = np.array([6e-3, 3e-3])
delta_max = 3e-2
beta_inj  = np.array([3.0, 3.0])

home_dir = os.path.join(
    os.environ["HOME"], "Nextcloud", "thor_scsi", "JB", "MAX_IV")
lat_name = sys.argv[1]
file_name = os.path.join(home_dir, lat_name+".lat")

lat_prop = lp.lattice_properties_class(gtpsa_prop, file_name, E_0, cod_eps)

lat_prop.prt_lat("lat_prop_lat.txt")

print("\nCircumference [m]      = {:7.5f}".format(lat_prop.compute_circ()))
print("Total bend angle [deg] = {:7.5f}".format(lat_prop.compute_phi_lat()))

try:
    # Compute Twiss parameters along lattice.
    if not lat_prop.comp_per_sol():
        print("\ncomp_per_sol: unstable")
        raise ValueError

    # Compute radiation properties.
    if not lat_prop.compute_radiation():
        print("\ncompute_radiation: unstable")
        raise ValueError
except ValueError:
    exit
else:
    lat_prop.prt_lat_param()
    lat_prop.prt_rad()
    lat_prop.prt_M()
    lat_prop.prt_M_rad()

uc_list = []
uc_list.append(lat_prop._lattice.find("ucborder", 0).index)
uc_list.append(lat_prop._lattice.find("ucborder", 1).index)
if True:
    uc_list.append(lat_prop._lattice.find("ucborder", 2).index)
uc_list = np.array(uc_list)

sp_list = np.zeros(2, dtype=int)
sp_list[0] = lat_prop._lattice.find("lsborder", 0).index
sp_list[1] = lat_prop._lattice.find("lsborder", 1).index

print("\nunit cell entrance           {:5s} loc = {:d}".
      format(lat_prop._lattice[uc_list[0]].name, uc_list[0]))
print("unit cell exit               {:5s} loc = {:d}".
      format(lat_prop._lattice[uc_list[1]].name, uc_list[1]))
if len(uc_list) == 3:
    print("next unit cell exit          {:5s} loc = {:d}".
          format(lat_prop._lattice[uc_list[2]].name, uc_list[2]))
print("super period first sextupole {:5s} loc = {:d}".
      format(lat_prop._lattice[sp_list[0]].name, sp_list[0]))
print("super period last sextupole  {:5s} loc = {:d}".
      format(lat_prop._lattice[sp_list[1]].name, sp_list[1]))

d2_list = ["d2_f1_sl_d0a", "d2_f1_sl_d0b", "d2_f1_sl_d0c", "d2_f1_sl_df1",
           "d2_f1_sl_df2", "d2_f1_sl_df3", "d2_f1_sl_df4", "d2_f1_sl_df5"]

d1_list = [
    "d1_f1_sl_ds6", "d1_f1_sl_ds5", "d1_f1_sl_ds4", "d1_f1_sl_ds3",
    "d1_f1_sl_ds2", "d1_f1_sl_ds1", "d1_f1_sl_ds0",
    "d1_f1_sl_dm1", "d1_f1_sl_dm2", "d1_f1_sl_dm3", "d1_f1_sl_dm4",
    "d1_f1_sl_dm5"
]

d1_bend = pc.bend_class(lat_prop, d1_list, phi_max, b_2_max)
d2_bend = pc.bend_class(lat_prop, d2_list, phi_max, b_2_max)

b_3_list = ["s3_f1", "s4_f1"]
nld = nld_cl.nonlin_dyn_class(lat_prop, A_max, beta_inj, delta_max, b_3_list)

if False:
    nld.zero_mult(lat_prop, 3)
if False:
    nld.zero_mult(lat_prop, 4)
if False:
    nld.set_xi(lat_prop, 0e0, 0e0)

step = 1;

if step == 1:
    weight = np.array([
        1e15,  # eps_x.
        1e5,   # alpha_c.
        1e-15, # U_0.
        1e2,   # etap_x_uc.
        1e-2,  # alpha_uc.
        1e0,   # nu_uc_x.
        1e0,   # nu_uc_y.
        1e2,   # eta_x.
        1e-6,  # nu_sp_x.
        1e-6,  # nu_sp_y.
        1e-4,  # beta_x.
        0e-5,  # beta_y.
        0e-3,  # dnu_x.
        0e-3,  # dnu_y.
        1e-5,  # xi.
        0e6,   # Im{h} rms.
        1e6    # K rms.
    ])

    prms = [
        ("q0_f1", "phi"),
        ("q0_f1", "b_2"),

        ("q1_f1", "b_2"),
        ("q2_f1", "b_2"),
        ("q3_f1", "b_2"),
        ("r1_f1", "b_2"),

        ("b_2_bend", d2_bend),
        ("b_2_bend", d1_bend),

        ("d1_f1_sl_ds6", "phi"),
        ("d1_f1_sl_ds5", "phi"),
        ("d1_f1_sl_ds4", "phi"),
        ("d1_f1_sl_ds3", "phi"),
        ("d1_f1_sl_ds2", "phi"),
        ("d1_f1_sl_ds1", "phi"),
        ("d1_f1_sl_ds0", "phi"),
        ("d1_f1_sl_dm1", "phi"),
        ("d1_f1_sl_dm2", "phi"),
        ("d1_f1_sl_dm3", "phi"),
        ("d1_f1_sl_dm4", "phi"),
        ("d1_f1_sl_dm5", "phi"),

        ("d2_f1_sl_d0a", "phi"),
        ("d2_f1_sl_d0b", "phi"),
        ("d2_f1_sl_d0c", "phi"),
        ("d2_f1_sl_df1", "phi"),
        ("d2_f1_sl_df2", "phi"),
        ("d2_f1_sl_df3", "phi"),
        ("d2_f1_sl_df4", "phi"),
        ("d2_f1_sl_df5", "phi"),

        ("s3_f1",    "b_3"),
        ("s4_f1",    "b_3")
    ]

    dprm_list = np.array([
        1e-3, 1e-3,
        1e-3, 1e-3, 1e-3, 1e-3,
        1e-3, 1e-3,
        1e-3, 1e-3, 1e-3, 1e-3, 1e-3, 1e-3,
        1e-3, 1e-3, 1e-3, 1e-3, 1e-3, 1e-3,
        1e-3, 1e-3, 1e-3, 1e-3, 1e-3, 1e-3, 1e-3, 1e-3
    ])
elif step == 2:
    weight = np.array([
        1e15,  # eps_x.
        1e7,   # alpha_c.
        0e-17, # U_0.
        1e2,   # etap_x_uc.
        1e-2,  # alpha_uc.
        1e-1,  # nu_uc_x.
        1e-1,  # nu_uc_y.
        1e0,   # eta_x.
        1e-5,  # nu_sp_x.
        0e-3,  # nu_sp_y.
        1e-4,  # beta_x.
        0e-6,  # beta_y.
        0e-2,  # dnu_x.
        0e-2,  # dnu_y.
        1e-1,  # xi.
        0e6,   # Im{h} rms.
        1e6    # K rms.
    ])

    prms = [
        # Note, the Powell optimiser intialises by first optimising each
        # parameter in the list.
        ("q1_f1" , "b_2"),
        ("q2_f1",  "b_2"),
        ("q3_f1",  "b_2"),
        # ("q4_h",  "b_2"),
        ("r1_f1",  "b_2"),

        ("b_2_bend", d2_bend),
        ("b_2_bend", d1_bend),

        # ("phi_bend", d2_bend),
        # ("r1",       "phi")

        # ("s1_f1",    "b_3"),
        # ("s2_f1",    "b_3"),
        ("s3_f1",    "b_3"),
        ("s4_f1",    "b_3"),

        # ("o1_f1_sl", "b_4"),
        # ("o2_f1_sl", "b_4"),
        # ("o3_f1_sl", "b_4"),
    ]

    dprm_list = np.array([
        1e-2, 1e-2, 1e-2, 1e-2, 1e-2, 1e-2,
        1e-1, 1e-1,
        # 1e-1, 1e-1,
        # 1e1, 1e1, 1e1,
    ])
elif step == 3:
    weight = np.array([
        1e18,  # eps_x.
        1e0,   # alpha_c.
        0e-17, # U_0.
        1e2,   # etap_x_uc.
        1e-2,  # alpha_uc.
        0e0,   # nu_uc_x.
        0e0,   # nu_uc_y.
        1e0,   # eta_x.
        0e-7,  # nu_sp_x.
        0e-3,  # nu_sp_y.
        0e-6,  # beta_x.
        0e-6,  # beta_y.
        0e-2,  # dnu_x.
        0e-2,  # dnu_y.
        0e-2,  # xi.
        0e6,   # Im{h} rms.
        1e8    # K rms.
    ])

    prms = [
        ("q1",    "b_2"),
        ("q2",    "b_2"),
        ("q3",    "b_2"),
        ("r1",    "b_2"),

        ("d2_0",  "b_2"),
        ("d2_1",  "b_2"),
        ("d2_2",  "b_2"),
        ("d2_3",  "b_2"),
        ("d2_4",  "b_2"),
        ("d2_5",  "b_2"),

        ("d1_u6", "b_2"),
        ("d1_u5", "b_2"),
        ("d1_u4", "b_2"),
        ("d1_u3", "b_2"),
        ("d1_u2", "b_2"),
        ("d1_u1", "b_2"),
        ("d1_0",  "b_2"),
        ("d1_d1", "b_2"),
        ("d1_d2", "b_2"),
        ("d1_d3", "b_2"),
        ("d1_d4", "b_2"),
        ("d1_d5", "b_2"),

        ("d2_0",  "phi"),
        ("d2_1",  "phi"),
        ("d2_2",  "phi"),
        ("d2_3",  "phi"),
        ("d2_4",  "phi"),
        ("d2_5",  "phi"),

        # ("r1",    "phi"),

        ("s1",      "b_3"),
        ("s2",      "b_3"),
        ("s3",      "b_3"),
        ("s4",      "b_3"),

        ("o1",      "b_4"),
        ("o2",      "b_4"),
        ("o3",      "b_4")
    ]

prm_list = pc.prm_class(lat_prop, prms, b_2_max)

rb = "r1_f1"

opt_sp = opt_sp_class(
    lat_prop, prm_list, dprm_list, uc_list, sp_list, weight, d1_bend, d2_bend,
    rb, eps_x_des, nu_uc_des, nu_sp_des, beta_des, dnu_des, nld)

opt_sp.opt_sp()
