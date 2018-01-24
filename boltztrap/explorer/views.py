"""This module provides the views for the boltztrap explorer interface."""

import os
from django.shortcuts import render_to_response
from django.template import RequestContext
from mpcontribs.rest.views import get_endpoint
from mpcontribs.io.core.components import render_dataframe, render_plot
from mpcontribs.io.core.recdict import render_dict

def index(request):
    ctx = RequestContext(request)
    if request.user.is_authenticated():
        API_KEY = request.user.api_key
        ENDPOINT = request.build_absolute_uri(get_endpoint())
        from ..rest.rester import BoltztrapRester
        with BoltztrapRester(API_KEY, endpoint=ENDPOINT) as mpr:
            try:
                prov = mpr.get_provenance()
                title = prov.get('title')
                provenance = render_dict(prov, webapp=True)
                tables = {}
                for doping in ['n', 'p']:
                    df = mpr.get_contributions(doping=doping)
                    tables[doping] = render_dataframe(df, webapp=True)
            except Exception as ex:
                ctx.update({'alert': str(ex)})
    else:
        ctx.update({'alert': 'Please log in!'})
    return render_to_response("boltztrap_explorer_index.html", locals(), ctx)
