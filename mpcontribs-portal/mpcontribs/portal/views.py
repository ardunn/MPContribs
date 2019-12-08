"""This module provides the views for the portal."""

import os
import json
import nbformat
from nbconvert import HTMLExporter
from bs4 import BeautifulSoup
from fido.exceptions import HTTPTimeoutError

from django.shortcuts import render
from django.template import RequestContext
from django.http import HttpResponse
from django.urls import reverse

from mpcontribs.client import load_client
from webtzite import get_client_kwargs

def index(request):
    ctx = RequestContext(request)
    ctx['landing_pages'] = []
    kwargs = get_client_kwargs(request)
    mask = ['project', 'title', 'authors']
    client = load_client()  # sets/returns global variable
    provenances = client.projects.get_entries(_fields=mask, **kwargs).response().result
    for provenance in provenances['data']:
        entry = {'project': provenance['project']}
        img_path = os.path.join(os.path.dirname(__file__), 'assets', 'images', provenance['project'] + '.jpg')
        if not os.path.exists(img_path):
            entry['contribs'] = client.contributions.get_entries(
                project=provenance['project'], **kwargs  # default limit 20
            ).response().result['data']
        entry['title'] = provenance['title']
        authors = provenance['authors'].split(',', 1)
        prov_display = f'<br><span style="font-size: 13px;">{authors[0]}'
        if len(authors) > 1:
            prov_display += '''<button class="btn btn-sm btn-link" data-html="true"
            data-toggle="tooltip" data-placement="bottom" data-container="body"
            title="{}" style="padding: 0px 0px 2px 5px;">et al.</a>'''.format(
                authors[1].strip().replace(', ', '<br/>'))
            prov_display += '</span>'
        entry['provenance'] = prov_display
        ctx['landing_pages'].append(entry)  # visibility governed by is_public flag and X-Consumer-Groups header
    return render(request, "mpcontribs_portal_index.html", ctx.flatten())


def export_notebook(nb, cid):
    nb = nbformat.from_dict(nb)
    html_exporter = HTMLExporter()
    html_exporter.template_file = 'basic'
    body = html_exporter.from_notebook_node(nb)[0]
    soup = BeautifulSoup(body, 'html.parser')
    # mark cells with special name for toggling, and
    # TODO make element id's unique by appending cid (for ingester)
    for div in soup.find_all('div', 'output_wrapper'):
        script = div.find('script')
        if script:
            script = script.contents[0]
            if script.startswith('render_json'):
                div['name'] = 'HData'
            elif script.startswith('render_table'):
                div['name'] = 'Table'
            elif script.startswith('render_plot'):
                div['name'] = 'Graph'
        else:
            pre = div.find('pre')
            if pre and pre.contents[0].startswith('Structure'):
                div['name'] = 'Structure'
    # name divs for toggling code_cells
    for div in soup.find_all('div', 'input'):
        div['name'] = 'Code'
    # separate script
    script = []
    for s in soup.find_all('script'):
        script.append(s.text)
        s.extract()  # remove javascript
    return soup.prettify(), '\n'.join(script)


def contribution(request, cid):
    ctx = RequestContext(request)
    kwargs = get_client_kwargs(request)
    client = load_client()
    try:
        nb = client.notebooks.get_entry(pk=cid, **kwargs).response(timeout=2).result
        if len(nb['cells']) < 2:
            raise HTTPTimeoutError
        ctx['nb'], ctx['js'] = export_notebook(nb, cid)
    except HTTPTimeoutError:
        ctx['alert'] = 'First build of detail page ongoing. Automatic reload in 10s.'
    return render(request, "mpcontribs_portal_contribution.html", ctx.flatten())


def cif(request, sid):
    client = load_client()
    kwargs = get_client_kwargs(request)
    cif = client.structures.get_entry(sid=sid, _fields=['cif'], **kwargs).response().result['cif']
    if cif:
        return HttpResponse(cif, content_type='text/plain')
    return HttpResponse(status=404)


def download_json(request, cid):
    client = load_client()
    kwargs = get_client_kwargs(request)
    contrib = client.contributions.get_entry(pk=cid, **kwargs).response().result
    if contrib:
        jcontrib = json.dumps(contrib)
        response = HttpResponse(jcontrib, content_type='application/json')
        response['Content-Disposition'] = 'attachment; filename={}.json'.format(cid)
        return response
    return HttpResponse(status=404)
