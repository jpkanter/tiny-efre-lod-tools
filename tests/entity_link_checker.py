#!/usr/bin/env python3

import sys
import json
import argparse
import requests
import xml.etree.ElementTree as ET
from es2json import esfatgenerator
from es2json import eprint
from es2json import isint
from es2json import litter


def check_other_indices(ppn):
    r = requests.get("https://data.slub-dresden.de/swb/{ppn}".format(ppn=ppn))
    if r.ok:
        return True
    return False


def check_rawdata(index, ppn):
    if index == "resources":
        url = "https://data.slub-dresden.de/source/kxp-de14/{ppn}".format(ppn=ppn)
    else:
        url = "https://data.slub-dresden.de/source/swb-aut/{ppn}".format(ppn=ppn)
    r = requests.get(url)
    if r.ok:
        return True
    return False


def check_swb(ppn):
    sru_xml_data = requests.get("http://swb2.bsz-bw.de/sru/DB=2.1/username=/password=/&operation=searchRetrieve&maximumRecords=10&recordSchema=dc&query=pica.ppn:{ppn}".format(ppn=ppn))
    if sru_xml_data.ok:
        num_of_records = ET.fromstring(sru_xml_data.content).find("{http://www.loc.gov/zing/srw/}numberOfRecords").text
        if int(num_of_records) > 0:
            return True
    return False


def traverse(dict_or_list, path):
    """
    iterate through a python dict or list, yield all the values
    """
    iterator = None
    if isinstance(dict_or_list, dict):
        iterator = dict_or_list.items()
    elif isinstance(dict_or_list, list):
        iterator = enumerate(dict_or_list)
    elif isinstance(dict_or_list, str):
        strarr = []
        strarr.append(dict_or_list)
        iterator = enumerate(strarr)
    else:
        return
    if iterator:
        for k, v in iterator:
            yield path + str([k]), v
            if isinstance(v, (dict, list)):
                for k, v in traverse(v, path + str([k])):
                    yield k, v

def run():
    parser = argparse.ArgumentParser(description='Test your internal open data links!')
    parser.add_argument(
        '-server', type=str, help="use http://host:port/index/type/id, id and type are optional, point to your local backend elasticsearch index")
    parser.add_argument(
        '-base_uri', type=str, help="use http://opendata.yourinstitution.org, determinate which base_uri should be tested.")
    args = parser.parse_args()
    
    if not args.server:
        eprint("error, -server argument missing!")
        exit(-1)
    slashsplit = args.server.split("/")
    host = slashsplit[2].rsplit(":")[0]
    if isint(args.server.split(":")[2].rsplit("/")[0]):
        port = args.server.split(":")[2].split("/")[0]
    index = args.server.split("/")[3]
    if len(slashsplit) > 4:
        doc_type = slashsplit[4]
        _id = None
    if len(slashsplit) > 5:
        if "?pretty" in args.server:
            pretty = True
            _id = slashsplit[5].rsplit("?")[0]
        else:
            _id = slashsplit[5]

    header = {"Content-type": "Application/json"}
    sys.stdout.write("{},{},{},{},{},{}\n".format("subject",
                                                               "path",
                                                               "missing object",
                                                               "wrong index?",
                                                               "found in rawdata",
                                                               "existent in swb"))
    sys.stdout.flush()
    for records in esfatgenerator(host=host, port=port, index=index, type=doc_type):
        mget_body = {"docs": []}
        target_source_map = {}
        for record in records:
            for key, value in traverse(record["_source"], ""):
                if isinstance(value, str) and value.startswith(args.base_uri):
                    if "source" in value:
                        continue
                    elif "swb" in value:
                        continue
                    mget_body["docs"].append({"_index":value.split("/")[-2],"_id":value.split("/")[-1]})
                    if not value in target_source_map:
                        target_source_map[value] = []
                    target_source_map[value].append({key: record["_source"]["@id"]})
        if mget_body["docs"]:
            r = requests.post("http://{host}:{port}/_mget".format(host=host,port=port), json=mget_body, headers=header)
            for doc in r.json().get("docs"):
                if doc.get("found"):
                    continue
                else:
                    #print(json.dumps(doc))
                    
                    for obj in target_source_map[args.base_uri+"/"+doc["_index"]+"/"+doc["_id"]]:
                        for key, base in obj.items():
                            attrib = args.base_uri+"/"+doc["_index"]+"/"+doc["_id"]
                            sys.stdout.write("{},{},{},{},{},{}\n".format(base,
                                                                       key,
                                                                       attrib,
                                                                       check_other_indices(attrib.split("/")[-1]),
                                                                       check_rawdata(doc["_index"],attrib.split("/")[-1]),
                                                                       check_swb(attrib.split("/")[-1])))
                            sys.stdout.flush()


if __name__ == "__main__":
    run()
