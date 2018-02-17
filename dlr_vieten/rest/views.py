# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from webtzite import mapi_func
import pandas as pd
from scipy.constants import pi, R
from scipy.optimize import brentq
from webtzite.connector import ConnectorBase
from mpcontribs.rest.views import Connector
ConnectorBase.register(Connector)

@mapi_func(supported_methods=["POST", "GET"], requires_api_key=True)
def index(request, db_type=None, mdb=None):
    try:
        cid = '5a8687dc7b4b7e0bc8433fe0'
        pars = mdb.contrib_ad.query_contributions(
            {'_id': cid}, projection={'_id': 0, 'content.pars': 1}
        )[0]['content']['pars']
        for k, v in pars.items():
            if isinstance(v, dict):
                pars[k] = dict((kk, float(x)) for kk, x in v.items())
            elif not v[0].isalpha():
                pars[k] = float(v)

        temp = 800
        temp += 273.15 # Celsius vs Kelvin / decide via unit?
        x_val = pd.np.log(pd.np.logspace(-5, -1, num=100)) # pd.np.log10(p_min, p_max)
        resiso = []
        a, b = 1e-10, 0.5-1e-10

        for xv in x_val:
            args = (temp, xv, pars)
            try:
                solutioniso = brentq(funciso, a, b, args=args)
            except ValueError:
                solutioniso = a if abs(funciso(a, *args)) < abs(funciso(b, *args)) else b
            resiso.append(solutioniso)

        ##print pd.np.exp(x_val)
        response = resiso
    except Exception as ex:
        raise ValueError('"REST Error: "{}"'.format(str(ex)))
    return {"valid_response": True, 'response': response}

def funciso(delta, T, x, p):
    d_delta = delta - p['delta_0']
    dh = enth_arctan(d_delta, *(p['fit_param_enth'].values())) * 1000.
    ds_pars = p['fit_par_ent'].values() + [p['act_mat'].values()[0], p['fit_param_fe'].values()]
    ds = entr_mixed(delta-p['fit_par_ent']['c'], *ds_pars)
    return dh - x*ds + R*T*x/2

def enth_arctan(x, dh_max, dh_min, t, s):
    """
    arctan function to fit enthalpy values of solid solutions
    :param x:       Delta_delta, change in non-stoichiometric redox extent vs. a reference
    :param t:       transition point; x value at which the reaction enthalpy of the solid solution
                    is exactly the average of dh_max and dh_min
    :param s:       slope, measure for the preference of B species reduction over A species reduction
    """
    return (((dh_max - dh_min) / pi) * (pd.np.arctan((x - t) * s) + (pi / 2))) + dh_min

def entr_fe(x, fit_param_fe):
    """
    Calculates the entropy values for SrFeOx based on the fit parameters in fit_param_fe
    :param x:               absolute delta
    :return:                dS of SrFeOx at delta = x with delta_0 accounted for
    """
    return fit_param_fe[0]/2 + fit_param_fe[1] + (2*fit_param_fe[2]*R * (pd.np.log(0.5-x) - pd.np.log(x)))

def entr_mixed(x, s, shift, delta_0, act_s1, fit_param_fe):
    """
    Returns a fit function for entropies based on the arctan function and the dilute species model fit of SrFeOx
    (see docstring in Atanfit.entropy)
    :param x:               absolute delta
    :param s:               slope, measure for the preference of B species reduction over A species reduction
    :param shift:           constant entropy shift
    :param delta_0:         shift from absolute delta
    :return:                dS of solid solution at delta = x with delta_0
    """
    efe = entr_fe(x+delta_0, fit_param_fe)
    return ((act_s1*efe)/pi) * (pd.np.arctan((x-delta_0)*s)+pi/2) + (1-act_s1)*efe + shift

