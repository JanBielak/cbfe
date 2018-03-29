from traits.api import implements, Int, Array, HasTraits, Instance, \
    Property, cached_property, Constant, Float, List
from ibvpy.api import BCDof
from ibvpy.fets.fets_eval import FETSEval, IFETSEval
from ibvpy.mats.mats1D import MATS1DElastic
from ibvpy.mats.mats1D5.mats1D5_bond import MATS1D5Bond
from ibvpy.mesh.fe_grid import FEGrid
from mathkit.matrix_la.sys_mtx_assembly import SysMtxAssembly
import matplotlib.pyplot as plt
import numpy as np
import sys
from scipy.interpolate import interp1d


class MATSEval(HasTraits):

    E_m = Float(28484., tooltip='Stiffness of the matrix',
                auto_set=False, enter_set=False)

    E_f = Float(170000., tooltip='Stiffness of the fiber',
                auto_set=False, enter_set=False)

    slack = 0.002

#     def reinf_law(self, eps_f):
#         return 1. * eps_f * (eps_f < self.slack) + (self.E_f * (eps_f - self.slack) + 0.002) * (eps_f >= self.slack)
#
#     def E_reinf(self, eps_f):
#         return 1. * (eps_f < self.slack) + self.E_f * (eps_f >= self.slack)

#     reinf_law_x = np.array([0.,  0.00041667,  0.00083333,  0.00125,  0.00166667,
#                             0.00208333,  0.0025,  0.00291667,  0.00333333,  0.00375,
#                             0.00416667,  0.00458333,  0.005,  0.00541667,  0.00583333,
#                             0.00625,  0.00666667,  0.00708333,  0.0075,  0.00791667,
#                             0.00833333,  0.00875,  0.00916667,  0.00958333,  0.01, 10])
#     reinf_law_y = np.array([0.,    30.25137058,    60.50274116,    90.75411175,
#                             121.00548233,   151.25685291,   180.78967788,   213.84723224,
#                             254.26299789,   301.27136355,   353.11307389,   409.66935019,
#                             469.9029913,   533.34632707,   597.82635842,   666.09922046,
#                             738.02173445,   811.21614618,   884.57900091,   961.54921197,
#                             1038.34892872,  1116.13154294,  1195.10676351,  1275.96327356,
#                             1351.38206049, 1351.38206049 + 170000. * 9.99])
#
#     def reinf_law(self, x):
#         return np.sign(x) * np.interp(np.abs(x), self.reinf_law_x, self.reinf_law_y)
#
#     def E_reinf(self, x):
#         d = np.diff(self.reinf_law_y) / np.diff(self.reinf_law_x)
#         d = np.append(d, d[-1])
#         E = interp1d(
#             self.reinf_law_x, d, kind='zero', fill_value=(0, 0), bounds_error=False)
#
#         print x
#         print E(np.abs(x))
#
#         print dsfs
#
#         return E(np.abs(x))

    a = 53472222.2222
    b = 10352083.3333
    k = 40000.

#     def reinf_law(self, x):
#         a = self.a * x ** 3 + self.b * x ** 2 + self.k * x
#         b = self.a * 0.006 ** 3 + self.b * \
#             0.006 ** 2 + self.k * 0.006 + 170000. * (x - 0.006)
#         return a * (x < 0.006) + b * (x >= 0.006)
#
#     def E_reinf(self, x):
#         a = 3. * self.a * x ** 2 + 2. * self.b * x + self.k
#         b = 170000.
#         return a * (x < 0.006) + b * (x >= 0.006)

    def reinf_law(self, x):
        return self.E_f * x

    def E_reinf(self, x):
        return self.E_f * np.ones_like(x)

    slip = List
    bond = List

    def b_s_law(self, x):
        return np.sign(x) * np.interp(np.abs(x), self.slip, self.bond)

    def G(self, x):
        d = np.diff(self.bond) / np.diff(self.slip)
        d = np.append(d, d[-1])
        G = interp1d(
            np.array(self.slip), d, kind='zero', fill_value=(0, 0), bounds_error=False)
#         y = np.zeros_like(x)
#         y[x < self.slip[0]] = d[0]
#         y[x > self.slip[-1]] = d[-1]
#         x[x < self.slip[0]] = self.slip[-1] + 10000.
#         y[x <= self.slip[-1]] = G(x[x <= self.slip[-1]])
#         return np.sign(x) * y
        return G(np.abs(x))

    n_e_x = Float

    def get_corr_pred(self, eps, d_eps, sig, t_n, t_n1):
        n_e, n_ip, n_s = eps.shape
        D = np.zeros((n_e, n_ip, 3, 3))
        D[:, :, 0, 0] = self.E_m
        D[:, :, 1, 1] = self.G(eps[:,:, 1])
        D[:, :, 2, 2] = self.E_reinf(eps[:,:, 2])

        d_sig = np.einsum('...st,...t->...s', D, d_eps)
        sig += d_sig
        sig[:, :, 1] = self.b_s_law(eps[:,:, 1])
        sig[:, :, 2] = self.reinf_law(eps[:,:, 2])

        return sig, D

    n_s = Constant(3)


class FETS1D52ULRH(FETSEval):

    '''
    Fe Bar 2 nodes, deformation
    '''

    implements(IFETSEval)

    debug_on = True

    A_m = Float(120. * 13. - 9. * 1.85, desc='matrix area [mm2]')
    A_f = Float(9. * 1.85, desc='reinforcement area [mm2]')
    L_b = Float(1., desc='perimeter of the bond interface [mm]')

    # Dimensional mapping
    dim_slice = slice(0, 1)

    n_nodal_dofs = Int(2)

    dof_r = Array(value=[[-1], [1]])
    geo_r = Array(value=[[-1], [1]])
    vtk_r = Array(value=[[-1.], [1.]])
    vtk_cells = [[0, 1]]
    vtk_cell_types = 'Line'

    n_dof_r = Property
    '''Number of node positions associated with degrees of freedom. 
    '''
    @cached_property
    def _get_n_dof_r(self):
        return len(self.dof_r)

    n_e_dofs = Property
    '''Number of element degrees
    '''
    @cached_property
    def _get_n_dofs(self):
        return self.n_nodal_dofs * self.n_dof_r

    def _get_ip_coords(self):
        offset = 1e-6
        return np.array([[-1 + offset, 0., 0.], [1 - offset, 0., 0.]])

    def _get_ip_weights(self):
        return np.array([1., 1.], dtype=float)

    # Integration parameters
    #
    ngp_r = 2

    def get_N_geo_mtx(self, r_pnt):
        '''
        Return geometric shape functions
        @param r_pnt:
        '''
        r = r_pnt[0]
        N_mtx = np.array([[0.5 - r / 2., 0.5 + r / 2.]])
        return N_mtx

    def get_dNr_geo_mtx(self, r_pnt):
        '''
        Return the matrix of shape function derivatives.
        Used for the conrcution of the Jacobi matrix.
        '''
        return np.array([[-1. / 2, 1. / 2]])

    def get_N_mtx(self, r_pnt):
        '''
        Return shape functions
        @param r_pnt:local coordinates
        '''
        return self.get_N_geo_mtx(r_pnt)

    def get_dNr_mtx(self, r_pnt):
        '''
        Return the derivatives of the shape functions
        '''
        return self.get_dNr_geo_mtx(r_pnt)


class TStepper(HasTraits):

    '''Time stepper object for non-linear Newton-Raphson solver.
    '''

    mats_eval = Instance(MATSEval, arg=(), kw={})  # material model

    fets_eval = Instance(FETS1D52ULRH, arg=(), kw={})  # element formulation

    A = Property(depends_on='fets_eval.A_f, fets_eval.A_m, fets_eval.L_b')
    '''array containing the A_m, L_b, A_f
    '''
    @cached_property
    def _get_A(self):
        return np.array([self.fets_eval.A_m, self.fets_eval.L_b, self.fets_eval.A_f])

    # number of elements
    n_e_x = Float(20.)

    # specimen length
    L_x = Float(75.)

    domain = Property(depends_on='n_e_x, L_x')
    '''Diescretization object.
    '''
    @cached_property
    def _get_domain(self):
        # Element definition
        domain = FEGrid(coord_max=(self.L_x,),
                        shape=(self.n_e_x,),
                        fets_eval=self.fets_eval)
        return domain

    bc_list = List(Instance(BCDof))

    J_mtx = Property(depends_on='n_e_x, L_x')
    '''Array of Jacobian matrices.
    '''
    @cached_property
    def _get_J_mtx(self):
        fets_eval = self.fets_eval
        domain = self.domain
        # [ d, n ]
        geo_r = fets_eval.geo_r.T
        # [ d, n, i ]
        dNr_geo = geo_r[:, :, None] * np.array([1, 1]) * 0.5
        # [ i, n, d ]
        dNr_geo = np.einsum('dni->ind', dNr_geo)
        # [ n_e, n_geo_r, n_dim_geo ]
        elem_x_map = domain.elem_X_map
        # [ n_e, n_ip, n_dim_geo, n_dim_geo ]
        J_mtx = np.einsum('ind,enf->eidf', dNr_geo, elem_x_map)
        return J_mtx

    J_det = Property(depends_on='n_e_x, L_x')
    '''Array of Jacobi determinants.
    '''
    @cached_property
    def _get_J_det(self):
        return np.linalg.det(self.J_mtx)

    B = Property(depends_on='n_e_x, L_x')
    '''The B matrix
    '''
    @cached_property
    def _get_B(self):
        '''Calculate and assemble the system stiffness matrix.
        '''
        mats_eval = self.mats_eval
        fets_eval = self.fets_eval
        domain = self.domain

        n_s = mats_eval.n_s

        n_dof_r = fets_eval.n_dof_r
        n_nodal_dofs = fets_eval.n_nodal_dofs

        n_ip = fets_eval.n_gp
        n_e = domain.n_active_elems
        #[ d, i]
        r_ip = fets_eval.ip_coords[:, :-2].T
        # [ d, n ]
        geo_r = fets_eval.geo_r.T
        # [ d, n, i ]
        dNr_geo = geo_r[:, :, None] * np.array([1, 1]) * 0.5
        # [ i, n, d ]
        dNr_geo = np.einsum('dni->ind', dNr_geo)

        J_inv = np.linalg.inv(self.J_mtx)

        # shape function for the unknowns
        # [ d, n, i]
        Nr = 0.5 * (1. + geo_r[:, :, None] * r_ip[None,:])
        dNr = 0.5 * geo_r[:, :, None] * np.array([1, 1])

        # [ i, n, d ]
        Nr = np.einsum('dni->ind', Nr)
        dNr = np.einsum('dni->ind', dNr)
        Nx = Nr
        # [ n_e, n_ip, n_dof_r, n_dim_dof ]
        dNx = np.einsum('eidf,inf->eind', J_inv, dNr)

        B = np.zeros((n_e, n_ip, n_dof_r, n_s, n_nodal_dofs), dtype='f')
        B_N_n_rows, B_N_n_cols, N_idx = [1, 1], [0, 1], [0, 0]
        B_dN_n_rows, B_dN_n_cols, dN_idx = [0, 2], [0, 1], [0, 0]
        B_factors = np.array([-1, 1], dtype='float_')
        B[:, :,:, B_N_n_rows, B_N_n_cols] = (B_factors[None, None,:] *
                                              Nx[:, :, N_idx])
        B[:, :,:, B_dN_n_rows, B_dN_n_cols] = dNx[:,:,:, dN_idx]

        return B

    def apply_essential_bc(self):
        '''Insert initial boundary conditions at the start up of the calculation.. 
        '''
        self.K = SysMtxAssembly()
        for bc in self.bc_list:
            bc.apply_essential(self.K)

    def apply_bc(self, step_flag, K_mtx, F_ext, t_n, t_n1):
        '''Apply boundary conditions for the current load increement
        '''
        for bc in self.bc_list:
            bc.apply(step_flag, None, K_mtx, F_ext, t_n, t_n1)

    def get_corr_pred(self, step_flag, d_U, eps, sig, t_n, t_n1):
        '''Function calculationg the residuum and tangent operator.
        '''
        mats_eval = self.mats_eval
        fets_eval = self.fets_eval
        domain = self.domain
        elem_dof_map = domain.elem_dof_map
        n_e = domain.n_active_elems
        n_dof_r, n_dim_dof = self.fets_eval.dof_r.shape
        n_nodal_dofs = self.fets_eval.n_nodal_dofs
        n_el_dofs = n_dof_r * n_nodal_dofs
        # [ i ]
        w_ip = fets_eval.ip_weights

        d_u_e = d_U[elem_dof_map]
        #[n_e, n_dof_r, n_dim_dof]
        d_u_n = d_u_e.reshape(n_e, n_dof_r, n_nodal_dofs)
        #[n_e, n_ip, n_s]
        d_eps = np.einsum('einsd,end->eis', self.B, d_u_n)

        # update strain
        eps += d_eps
#         if np.any(sig) == np.nan:
#             sys.exit()

        # material response state variables at integration point
        sig, D = mats_eval.get_corr_pred(eps, d_eps, sig, t_n, t_n1)

        # system matrix
        self.K.reset_mtx()
        Ke = np.einsum('i,s,einsd,eist,eimtf,ei->endmf',
                       w_ip, self.A, self.B, D, self.B, self.J_det)

        self.K.add_mtx_array(
            Ke.reshape(-1, n_el_dofs, n_el_dofs), elem_dof_map)

        # internal forces
        # [n_e, n_n, n_dim_dof]
        Fe_int = np.einsum('i,s,eis,einsd,ei->end',
                           w_ip, self.A, sig, self.B, self.J_det)
        F_int = -np.bincount(elem_dof_map.flatten(), weights=Fe_int.flatten())
        self.apply_bc(step_flag, self.K, F_int, t_n, t_n1)
        return F_int, self.K, eps, sig


class TLoop(HasTraits):

    ts = Instance(TStepper)
    d_t = Float(0.01)
    t_max = Float(1.0)
    k_max = Int(200)
    tolerance = Float(1e-6)

    def eval(self):

        self.ts.apply_essential_bc()

        t_n = 0.
        t_n1 = t_n
        n_dofs = self.ts.domain.n_dofs
        n_e = self.ts.domain.n_active_elems
        n_ip = self.ts.fets_eval.n_gp
        n_s = self.ts.mats_eval.n_s
        U_record = np.zeros(n_dofs)
        F_record = np.zeros(n_dofs)
        U_k = np.zeros(n_dofs)
        eps = np.zeros((n_e, n_ip, n_s))
        sig = np.zeros((n_e, n_ip, n_s))

        sf_record = np.zeros(2 * n_e)  # shear flow

        eps_f_record = np.zeros(2 * n_e)
        sig_m_record = np.zeros(2 * n_e)

        while t_n1 <= self.t_max:
            t_n1 = t_n + self.d_t
            k = 0
            step_flag = 'predictor'
            d_U = np.zeros(n_dofs)
            d_U_k = np.zeros(n_dofs)
            while k < self.k_max:
                R, K, eps, sig = self.ts.get_corr_pred(
                    step_flag, d_U_k, eps, sig, t_n, t_n1)

                F_ext = -R
                K.apply_constraints(R)
                d_U_k = K.solve()
                d_U += d_U_k
                if np.linalg.norm(R) < self.tolerance:
                    F_record = np.vstack((F_record, F_ext))
                    U_k += d_U
                    U_record = np.vstack((U_record, U_k))
                    sf_record = np.vstack((sf_record, sig[:, :, 1].flatten()))

                    sig_m_record = np.vstack((sig_m_record, sig[:, :, 0].flatten()))
                    eps_f_record = np.vstack((eps_f_record, eps[:, :, 2].flatten()))

                    break
                k += 1
                if k == self.k_max:
                    print 'nonconvergence'
                step_flag = 'corrector'

            t_n = t_n1
        return U_record, F_record, sf_record, sig_m_record, eps_f_record

if __name__ == '__main__':

    #=========================================================================
    # nonlinear solver
    #=========================================================================
    # initialization

    ts = TStepper()

    ts.L_x = 200

    ts.n_e_x = 20

#     ts.mats_eval.slip = [0.0, 0.09375, 0.505, 0.90172413793103456, 1.2506896551724138, 1.5996551724137933, 1.9486206896551728, 2.2975862068965522, 2.6465517241379315,
#                          2.9955172413793107, 3.34448275862069, 3.6934482758620693, 4.0424137931034485, 4.3913793103448278, 4.7403448275862079, 5.0893103448275863, 5.4382758620689664, 5.7000000000000002]
#
#     ts.mats_eval.bond = [0.0, 43.05618551913318, 40.888629416715574, 49.321970730383285, 56.158143245133338, 62.245706611484323, 68.251000923721875, 73.545464379399633, 79.032738465995692,
# 84.188949455670524, 87.531858162376921, 91.532666285021264,
# 96.66808302759236, 100.23305856244875, 103.01090365681807,
# 103.98920712455558, 104.69444418370917, 105.09318577617957]

#     ts.mats_eval.slip = [0, 0.1, 0.2, 0.22, 0.24, 0.26, 0.28, 0.3, 0.4, 0.5]
#     ts.mats_eval.bond = [0., 15., 30., 19., 17., 13., 7.,  5., 3., 1.]

    ts.mats_eval.slip = [0, 1e-8,  0.5]
    ts.mats_eval.bond = [0., 16., 16.]

    n_dofs = ts.domain.n_dofs

#     tf = lambda t: 1 - np.abs(t - 1)

#     ts.bc_list = [BCDof(var='u', dof=n_dofs - 2, value=0.0),
#                   BCDof(var='u', dof=n_dofs - 1, value=0.5)]

    ts.bc_list = [BCDof(var='u', dof=0, value=0.0),
                  BCDof(var='u', dof=1, value=0.0),
                  BCDof(var='u', dof=n_dofs - 1, value=0.5)]

    tl = TLoop(ts=ts)

    U_record, F_record, sf_record, sig_m_record, sig_f_record = tl.eval()
    n_dof = 2 * ts.domain.n_active_elems + 1
    plt.plot(U_record[:, n_dof], F_record[:, n_dof],
             marker='.', label='numerical')

    def avg_sig(sig):
        '''average the stress on the integration points to the nodes'''
        sig = np.hstack((sig[:, 0:1], sig, sig[:, -1::]))
        sig = (sig[:, 0::2] + sig[:, 1::2]) / 2.
        sig[:, -1] = 0.
        return sig

    sig_m = avg_sig(sig_m_record)
    X = np.linspace(0, ts.L_x, ts.n_e_x + 1)
    from scipy.interpolate import interp2d
    interp_m = interp2d(X[::-1], F_record[:, -1], sig_m)
    plt.figure()
    x = np.linspace(0, ts.L_x, 500)
    F_arr = np.linspace(0, np.amax(F_record[:, -1]), 20)

    am = 120. * 13. - 9. * 1.85
    af = 9. * 1.85
    A = am + af
    E_c = (ts.mats_eval.E_m * am + ts.mats_eval.E_f * af) / A

    F_arr = np.append(
        F_arr, [1.24999 * E_c / ts.mats_eval.E_m * A, 1.7325 * E_c / ts.mats_eval.E_m * A])
    F_arr.sort()

    sig_m_150 = []

    sm = plt.cm.ScalarMappable(
        cmap='Greys', norm=plt.Normalize(vmin=0, vmax=5))
    # fake up the array of the scalar mappable. Urgh...
    sm._A = [1, 2, 3, 4, 5]
    plt.colorbar(sm)

    def sig_m(z, sig_c):  # matrix stress
        T = 0.9
        sig_m = np.minimum(
            z * T * af / am, ts.mats_eval.E_m * sig_c / E_c)
        return sig_m

    for i, F in enumerate(F_arr):
        if F / A / E_c * ts.mats_eval.E_m < 1.25:
            plt.plot(x, np.ones_like(x) * F / A / E_c *
                     ts.mats_eval.E_m, 'k', alpha=float(i) / 21.)
            sig_m_150.append(F / A / E_c * ts.mats_eval.E_m)
        else:
            #             plt.plot(x, interp_m(x, F), 'k', alpha=float(i) / 21.)
            #             sig_m_150.append(interp_m(100., F))
            plt.plot(x, sig_m(x, F / A), 'k', alpha=float(i) / 21.)
            sig_m_150.append(sig_m(150., F / A))

    plt.xlabel('z')
    plt.ylabel('sig_m')

    plt.figure()
    plt.plot(F_arr / A, sig_m_150)

#     for i in np.arange(len(sig_m_150) - 1):
#         plt.plot([F_arr[i] / (120. * 13.), F_arr[i + 1] / (120. * 13.)],
#                  [sig_m_150[i], sig_m_150[i + 1]], 'k', alpha=float(i) / 200.)

    plt.xlabel('sig_c')
    plt.ylabel('sig_m at z = 150')

    plt.show()

#     ts.L_x = 200
#     U_record, F_record, sf_record, sig_m_record, sig_f_record = tl.eval()
#     n_dof = 2 * ts.domain.n_active_elems + 1
#     plt.plot(U_record[:, n_dof], F_record[:, n_dof],
#              marker='.', label='numerical')

#     plt.xlabel('displacement [mm]')
#     plt.ylabel('pull-out force [N]')
#     plt.ylim(0, 20000)
    plt.legend(loc='best')

    plt.show()
