"""
This module contains functions for mesh-based Monte Carlo variance reduction.
"""

from itertools import izip
from warnings import warn
from pyne.utils import VnVWarning

import numpy as np

warn(__name__ + " is not yet V&V compliant.", VnVWarning)

try:
    from itaps import iMesh, iBase, iMeshExtensions
except ImportError:
    warn("the PyTAPS optional dependency could not be imported. "
        "Some aspects of the variance reduction module may be incomplete.", 
        VnVWarning)

from mesh import Mesh
from mesh import MeshError
from mesh import IMeshTag
from mcnp import Wwinp

def cadis(adj_flux_mesh, adj_flux_tag, q_mesh, q_tag, 
          ww_mesh, ww_tag, q_bias_mesh, q_bias_tag, beta=5):
    """This function reads PyNE Mesh objects tagged with adjoint fluxes and 
    unbiased source densities and outputs PyNE Meshes of weight window lower 
    bounds and biased source densities as computed by the Consistant 
    Adjoint-Driven Importance Sampling (CADIS) method [1]. Note that values can be
    stored on the same Mesh object, all different Mesh objects, or any
    combination in between. Meshes can be structured or unstructured. 
    Note that this function is suitable for Forward Weighted (FW) CADIS as well,
    the only difference being the adjoint source used for the estimation of the 
    adjoint flux.

    [1] Haghighat, A. and Wagner, J. C., "Monte Carlo Variance Reduction with 
        Deterministic Importance Functions," Progress in Nuclear Energy, 
        Vol. 42, No. 1, pp. 25-53, 2003.

    Parameters
    ----------
    adj_flux_mesh : PyNE Mesh object
        The mesh containing the adjoint fluxes.
    adj_flux_tag : string
        The name of the adjoint flux tag on adj_mesh.
    q_mesh : PyNE Mesh object
        The mesh containing the unbiased source density.
    q_tag : string
        The name of the source density tag on q_mesh.
    ww_mesh : PyNE Mesh object
        The mesh to store the output weight window mesh.
    ww_tag : string
        Name of the tag to store output weight window values on ww_mesh.
    q_bias_mesh : PyNE Mesh object
        The mesh to store the output biased source density mesh.
    q_bias_tag : PyNE Mesh object 
        Name of the tag to store output weight window values on q_bias_mesh.
    beta : float
        The ratio of the weight window upper bound to the weight window lower
        bound. The default value is 5: the value used in MCNP. 
    """
    
    # find number of energy groups
    e_groups = adj_flux_mesh.mesh.getTagHandle(adj_flux_tag)[list(
                   adj_flux_mesh.mesh.iterate(iBase.Type.region, 
                                              iMesh.Topology.all))[0]]
    e_groups = np.atleast_1d(e_groups)
    num_e_groups = len(e_groups)

    # verify source (q) mesh has the same number of energy groups
    q_e_groups = q_mesh.mesh.getTagHandle(q_tag)[list(
                      q_mesh.mesh.iterate(iBase.Type.region, 
                                          iMesh.Topology.all))[0]]
    q_e_groups = np.atleast_1d(q_e_groups)
    num_q_e_groups = len(q_e_groups)

    if num_q_e_groups != num_e_groups:
        raise TypeError("{0} on {1} and {2} on {3} "
            "must be of the same dimension".format(adj_flux_mesh, adj_flux_tag, 
                                                   q_mesh, q_tag))

    # create volume element (ve) iterators
    adj_ves = adj_flux_mesh.mesh.iterate(iBase.Type.region, iMesh.Topology.all)
    q_ves = q_mesh.mesh.iterate(iBase.Type.region, iMesh.Topology.all)

    # calculate total source strength
    q_tot = 0
    for q_ve in q_ves:
        q_tot += np.sum(q_mesh.mesh.getTagHandle(q_tag)[q_ve]) \
                 *q_mesh.elem_volume(q_ve)

    q_ves.reset()

    # calculate the total response per source particle (R)
    R = 0
    for adj_ve, q_ve in zip(adj_ves, q_ves):
        adj_flux = adj_flux_mesh.mesh.getTagHandle(adj_flux_tag)[adj_ve]
        adj_flux = np.atleast_1d(adj_flux)
        q = q_mesh.mesh.getTagHandle(q_tag)[q_ve]
        q = np.atleast_1d(q)

        vol = adj_flux_mesh.elem_volume(adj_ve)
        for i in range(0, num_e_groups):
            R += adj_flux[i]*q[i]*vol/q_tot

    # generate weight windows and biased source densities using R
    tag_ww = ww_mesh.mesh.createTag(ww_tag, num_e_groups, float)
    ww_ves = ww_mesh.mesh.iterate(iBase.Type.region, iMesh.Topology.all)
    tag_q_bias = q_bias_mesh.mesh.createTag(q_bias_tag, num_e_groups, float) 
    q_bias_ves = q_bias_mesh.mesh.iterate(iBase.Type.region, iMesh.Topology.all)
    # reset previously created iterators
    q_ves.reset()
    adj_ves.reset()

    for adj_ve, q_ve, ww_ve, q_bias_ve in izip(adj_ves, q_ves, 
                                               ww_ves, q_bias_ves):
        adj_flux = adj_flux_mesh.mesh.getTagHandle(adj_flux_tag)[adj_ve]
        adj_flux = np.atleast_1d(adj_flux)
        q = q_mesh.mesh.getTagHandle(q_tag)[q_ve]
        q = np.atleast_1d(q)

        tag_q_bias[q_bias_ve] = [adj_flux[i]*q[i]/q_tot/R 
                                 for i in range(num_e_groups)]

        tag_ww[ww_ve] = [R/(adj_flux[i]*(beta + 1.)/2.) 
                         if adj_flux[i] != 0.0 else 0.0 
                         for i in range(num_e_groups)]


        tag_q_bias[q_bias_ve] = [adj_flux[i]*q[i]/R[i] 
                                 for i in range(0, num_e_groups)]

def magic(tally, tag_name, total=False):
    """Magic variance reduction technique
    Parameters:
        tally :: pyne meshtally obj
    """
    
    # Convert particle name to the recognized abreviation
    if tally.particle == "neutron":
        tally.particle = "n"
    elif tally.particle == "photon":
        tally.particle = "p"
    elif tally.particle == "electron":
        tally.particle = "e"
            
    
    if not total:
        # need to iterate through each energy group
        #root_tag = tally.mesh.createTag("e_upper_bounds",1,float)
        #root_tag[tally.mesh.rootSet] = tally.e_bounds

        for bound in tally.e_bounds:
            pass
    
    elif total:
        # only need total energy
        tally.vals = IMeshTag(1, float, mesh=tally, name=tag_name)
        tally.ww_x = IMeshTag(1, float, name="ww_{0}".format(tally.particle))
        
        root_tag = tally.mesh.createTag(
            "{0}_e_upper_bounds".format(tally.particle),1, float)
        root_tag[tally.mesh.rootSet] = np.max(tally.e_bounds[:])
        
        max_val = np.max(tally.vals[:])
        ww = []
        
        for ve, flux in enumerate(tally.vals):
            ww.append(tally.vals[ve]/(2*max_val))
        
        tally.ww_x = ww
        
        wwinp = Wwinp()
        wwinp.read_mesh(tally.mesh)
        wwinp.mesh.save("test.h5m")
        wwinp.write_wwinp("{0}".format(tag_name))
         
