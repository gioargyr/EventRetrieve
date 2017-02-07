import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from django.shortcuts import render

# Create your views here.
from django.http import HttpResponse
from django.utils.datastructures import MultiValueDictKeyError

def index(request):
    return HttpResponse("Please use the API call \"search\"<br>e.g., http://localhost:8000/eventDetection/search?extent=POINT(1%2010)&reference_date=2016-01-01&event_date=2017-01-01&keys=Camp")
def search(request):
    # Get the parameters from user
    try:
        extent=request.GET.get('extent','')
        keys=request.GET.get('keys','')
        event_date=request.GET.get('event_date','')
        reference_date=request.GET.get('reference_date','')
    except MultiValueDictKeyError as e:
        return HttpResponse('Missing parameters. Please provide all: <ol><li>extent</li><li>event_date</li><li>reference_date</li><li>keys</li></ol>')

    # try parsing dates according to ISO8601
    try:
        if event_date:
            event_date=datetime.strptime(event_date,"%Y-%m-%d")
        if reference_date:
            reference_date=datetime.strptime(reference_date,"%Y-%m-%d")
    except ValueError as e:
        return HttpResponse('date should be <b>ISO8601</b> format')
    
    if keys:
        keys = keys.replace(",", "|");

    q=query(extent,keys,event_date,reference_date)
    print(q)
    
    headers = {'content-type': 'application/x-www-form-urlencoded', 'Accept' : 'application/sparql-results+xml'}
    url = "http://semagrow_bde:8080/SemaGrow/sparql"
    params = {"query" : q, 'format':'SPARQL/XML'}
    r=requests.post(url, params=params, headers=headers)

    print(r.status_code, r.reason)
    print(r.text)
    # parse xml data to build the objects
    tree = ET.ElementTree(ET.fromstring(r.text))
    results=tree.find('{http://www.w3.org/2005/sparql-results#}results')
    events={}
    for result in results:
        bindings=result.findall('{http://www.w3.org/2005/sparql-results#}binding')
        #bindings[0][0].text # ignore this one
        event_id=bindings[1][0].text
        title=bindings[2][0].text
        date=bindings[3][0].text
        gwkt=bindings[4][0].text
        name=bindings[5][0].text
        event={'event_id':event_id,'title':title,'date':date,'geoemtries':[gwkt],'name':name}
        
        #if event's id already in our dictionary then add the new geometry to its list of geometries
        if event_id in events:
            events[event_id]['geometries'].append(gwkt)
        else:
            events[event_id]=event
    return HttpResponse(json.dumps(events) , content_type="application/json")

# Build the query
def query(extent,keys,event_date,reference_date):
    select ="SELECT distinct ?e ?id ?t ?d ?w ?n";
    #filters = "filter(";
    prefixes = '\n'.join(('PREFIX geo: <http://www.opengis.net/ont/geosparql#>',
    'PREFIX strdf: <http://strdf.di.uoa.gr/ontology#>',
    'PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>',
    'PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>',
    'PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>',
    'PREFIX ev: <http://big-data-europe.eu/security/man-made-changes/ontology#>'));
    where = '\n'.join(('WHERE{',' ?e rdf:type ev:NewsEvent . ', ' ?e ev:hasId ?id . ?e ev:hasTitle ?t . ',
    ' ?e ev:hasDate ?d . ','?e ev:hasArea ?a . ', '?a ev:hasName ?n . ',' ?a geo:hasGeometry ?g . ',  
    ' ?g geo:asWKT ?w .'));
    filters=[]
    if event_date:
        filters.append("?d < '" + str(event_date) + "'^^xsd:dateTime")
    if reference_date:
        filters.append("?d > '" + str(reference_date) + "'^^xsd:dateTime")
    if keys:
        filters.append("regex(?t, '" + str(keys) + "','i')")
    if extent:
        filters.append("strdf:intersects(?w,'" + str(extent) + "')")
    if filters:
        where += 'FILTER('+' && '.join(filters) + ")}"
    else:
        where += '}'

    q = '\n'.join((prefixes ,select , where ))
    return q
