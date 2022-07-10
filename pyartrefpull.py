#from urllib import response
from ast import arg
import json
from multiprocessing import context
import re
from time import sleep
from numpy import true_divide
from yaml import load, dump, Loader, Dumper
import csv

import argparse
import requests
import os
from math import ceil
from datetime import datetime
import cloudscraper
from playwright.sync_api import Playwright, sync_playwright
from concurrent.futures import as_completed
from requests_futures.sessions import FuturesSession

# ----------- playwright browser variables
#global variable 👿
playwrightPage = None

def initPlaywrightPage():
    global playwrightPage
    if playwrightPage is None:
        browser = sync_playwright().start().chromium.launch(headless=False)
        context = browser.new_context()
        playwrightPage = context.new_page()
    return playwrightPage

def closePlaywrightPage():
    global playwrightPage
    if playwrightPage is not None:
        context = playwrightPage.context
        browser = context.browser
        context.close()
        browser.close()
# ----------- get artstation data

def artRequest(url, querystring, payload="", headers={}):
    return requests.request("GET", url, data=payload, headers=headers, params=querystring)

def playwrightArtRequest(url):
    page = initPlaywrightPage()
    with page.expect_response(url) as response_info:
        page.goto(url, wait_until="load")
    response = response_info.value
    response.status_code = response.status #I fckg ❤ monkey patching
    response.text = response.text() #forgive me lord but this is too good 👿
    response.content = response.body()
    return response

def alternativeArtRequest(url):
    '''tries to get page content with cloudscraper then with playwright'''
    scraper = cloudscraper.create_scraper()
    response = scraper.get(url)
    if response.status_code != 200:  # retry seems to change stuff
        print(f"waiting 3sec for :{url}")
        sleep(3)
        response = scraper.get(url)
    if response.status_code != 200:
        #tries playwright
        response = playwrightArtRequest(url)
    return response


def getUserId(account_name):
    url = f"https://www.artstation.com/{account_name}"
    response = alternativeArtRequest(url)
    return re.search("\\\\\"user_id\\\\\":(.*?),", response.content.decode('utf_8')).group(1)
    #return "2069477"

def getUserCollections(user_id):
    # get artstation collections from user
    response = artRequest(
        "https://www.artstation.com/collections.json",
        {"user_id": f"{user_id}"}
    )
    return load(response.text, Loader=Loader) if response.status_code == 200 else None

def getUserCollectionByName(user_id,collection_name):
    collections = getUserCollections(user_id)
    for collection in collections:
        if collection['name'] == collection_name:
            return collection["id"]
    return None

def getUserLikes(account_name,page_id= 1):
    url = f"https://www.artstation.com/users/{account_name}/likes.json?page={page_id}"
    response = alternativeArtRequest(url)
    return load(response.text, Loader=Loader) if response.status_code == 200 else None

def getCollectionProjects(collection_id, page_id=1):
    response = artRequest(
        f"https://www.artstation.com/collections/{collection_id}/projects.json",
        {"collection_id": f"{collection_id}", "page": f"{page_id}"}
    )
    return load(response.text, Loader=Loader) if response.status_code == 200 else None

def getArtistProjects( artist_id, page_id = 1):
    url = f"https://www.artstation.com/users/{artist_id}/projects.json?page=1"
    response = alternativeArtRequest(url)
    return load(response.text, Loader=Loader) if response.status_code ==200 else None

def getProjectDetailsRequest(session : FuturesSession,project_id):
    url = f"https://www.artstation.com/projects/{project_id}.json"
    return session.get(url)
# ------------ set up library setting


def writeLibrarySettings(path, config, name=".pyartrefpull.yaml"):
    libFilename = os.path.join(path, name)
    with open(libFilename, 'w') as f_config:
        data = dump(config, Dumper=Dumper, default_flow_style=False)
        f_config.write(data)
    return os.path.exists(libFilename)  # return success status


def loadLibrarySettings(path, name=".pyartrefpull.yaml"):
    data = None
    if os.path.exists(os.path.join(path, name)) and os.path.isfile(os.path.join(path, name)):
        with open(os.path.join(path, name), 'r') as f_config:
            data = load(f_config, Loader=Loader)
    return data


def createSampleLib(path, name=".pyartrefpull.yaml"):
    return writeLibrarySettings(
        path,
        loadLibrarySettings(os.path.dirname(__file__),  # get the samplefile from the directory where pyartrefpull.py is
                            "sample_libSettings.yaml"),
        name
    )


def updateLibTime(path, name=".pyartrefpull.yaml", field="last_fetch"):
    config  = loadLibrarySettings(path,name)
    retvalue = False
    if (config):
        currentDate = datetime.now().strftime("%H:%M %d-%m-%Y")
        config[field] = currentDate
        retvalue = writeLibrarySettings(path,config,name)
    return retvalue
# ------------ set up cache file & check
cacheColumns = [
    "status",  
    "project_id",  
    "postsources",   #[s] # [col/id | art/id | pro/id]
    "protosources",   #[s] #user side all flavors
    "title",  
    "artist",  
    "categories",   #[s]
    "likes_count",  
    "views_count",  
    "comments_count",  
    "thumbnail_link",  
    "default_size",
]

def loadCacheFile(path,name=".artrefcache.csv"):
    outList = []
    csvColumns = None
    artDictionnary = {}
    if os.path.exists(os.path.join(path, name)) and os.path.isfile(os.path.join(path, name)):
        with open(os.path.join(path,name),'r') as csvFile:
            csvReader = csv.reader(csvFile,delimiter=',')
            isFirst = True
            i = 0
            nb_doublon = 0
            for row in csvReader:
                if isFirst:
                    csvColumns = row
                    isFirst=False
                else:
                    project_id = row[cacheColumns.index("project_id")]
                    if (not project_id in artDictionnary):
                        outList.append(row)
                        artDictionnary[project_id] = i
                        i += 1 
                    else:
                        nb_doublon += 1
                        print(f"Double entry in cache file, line {i+nb_doublon} :\n{project_id} has been ignored")
    return outList,csvColumns,artDictionnary


def saveCacheFile(path, data, name=".artrefcache.csv"):
    retValue = False
    with open(os.path.join(path, name),'w') as csvFile:
        csvWriter = csv.writer(csvFile, delimiter=',')
        csvWriter.writerows(data)
        retValue = True
    return retValue


def getProjectIndexInCache(cacheTuple,project_id):
    return cacheTuple[2].get(project_id,None)

def getProjectStatusInCache(cacheTuple,project_id):
    r'''returns : tuple (project status, [project postsource list])'''
    project_index = getProjectIndexInCache(cacheTuple, project_id)
    if project_index is not None:
        return (
            cacheTuple[0][project_index][cacheColumns.index("status")],
            cacheTuple[0][project_index][cacheColumns.index("postsources")],
            )
    else:
        return None

def setProjectStatusInCache(cacheTuple, project_id):
    pass
def addProjectToCache(cacheTuple, image_id):
    data , columns , project_mapping = cacheTuple
    project_id = image_id[cacheColumns.index("project_id")]
    if(getProjectIndexInCache(cacheTuple, project_id) is None):
        project_mapping[project_id] = len(data)
        data.append(image_id)
    return data, columns, project_mapping
# ------------ set up static website gen

def buildStaticWebsite(path):
    pass
#------------- cli helper functions
def computeSourceType(source):
    returnInput = source["type"]
    value = source["value"]
    pathLength = len(value.split('/'))
    if (returnInput == "collection"):
        if isinstance(value,int):
            return 'col_id'
        elif pathLength == 1: #NOTE assume that a username cant contain '/' for url reasons
            return 'col_user'
        elif pathLength > 1: 
            if value.split('/')[1] == "likes":
                return 'likes'
            else :
                return 'col_path'
    elif returnInput == "artist":
        return 'artist'
    elif returnInput == "project":
        return 'project'
    return ''

def stringifySource(source):
    return "\\".join([source["type"],source["value"]])


def processPages(requestFunction, request_id, sourceStr, cacheObj):
    retList = []
    allPagesRead = False
    maxPages = 1
    currentPage = 1
    while currentPage <= maxPages and allPagesRead == False:
        project_json = requestFunction(request_id, currentPage)
        if currentPage == 1:  # on the first page, determine the actual maximum number of pages
            maxPages = ceil(project_json["total_count"]/50)
        for project in project_json["data"]:
            status = 0
            project_id = project["hash_id"]
            projectStatus = getProjectStatusInCache(cacheObj, project_id)
            if projectStatus is not None:
                status = 1 if sourceStr in projectStatus[1] else 2
            if status != 1:
                tempProj = [
                    status,
                    project_id,
                    [sourceStr],
                    [],
                    project["title"],
                    project["user"]["username"],
                    [],
                    project["likes_count"],
                    None,
                    None,
                    project["cover"]["thumb_url"],
                    None,
                ]
                retList.append(tempProj)
            else:
                allPagesRead = True
                break
        currentPage += 1  # move to the next page
    return retList

def processArtist(username, cacheObj):
    '''output : list of list of projects  [project entry][status [0 not in cache, 1 in cache from this collection, 2 in cache from other source'''
    return processPages(getArtistProjects, username, f"art/{username}", cacheObj)

def processCollections(collection_id, cacheObj):
    '''output : list of list of projects  [project entry][status [0 not in cache, 1 in cache from this collection, 2 in cache from other source'''
    return processPages(getCollectionProjects, collection_id, f"col/{collection_id}", cacheObj)

def processLikes(username,cacheObj):
    '''output : list of list of projects  [project entry][status [0 not in cache, 1 in cache from this collection, 2 in cache from other source'''
    return processPages(getUserLikes, username, f"lik/{username}", cacheObj)

def addPostsource2Dic(dic,key,user_source):
    if key in dic:
        if user_source not in dic[key]:
            dic[key] += [user_source]
    else:
        dic[key] = [user_source]

def getPostSource(protoSources):
    r''' getPostSource : transform protoSource (user side) to postSource (software side).
    postSource have the advantage to be unique wrt the web request process.
    returns : dictionnary (sourceidentifier [col/id | art/id | ...] : protoSourceList exmp : collection\username)
    '''
    postSource = {}
    for source in protoSources:
        sourceType = computeSourceType(source)
        sourceStr = stringifySource(source)

        if sourceType == "col_id":
            addPostsource2Dic(postSource, f"col/{source['value']}", sourceStr)

        elif sourceType == "col_user":
            user_id = getUserId(source["value"])
            col_json = getUserCollections(user_id)
            for col in col_json:
                addPostsource2Dic(postSource, f"col/{col['id']}", sourceStr)
            addPostsource2Dic(postSource, f"lik/{source['value']}", sourceStr)

        elif sourceType == "likes": #assume pre treatment from computesourcetype
            addPostsource2Dic(postSource, f"lik/{source['value'].split('/')[0]}", sourceStr)

        elif sourceType == "col_path":  # assume pre treatment from computesourcetype (len(source value)> 1)
            user_id = getUserId(source["value"].split('/')[0])
            col_id = getUserCollectionByName(user_id,source["value"].split('/')[1])
            if col_id is not None:
                addPostsource2Dic(postSource, f"col/{col_id}", sourceStr)
            else :
                pass#TODO: error logging

        elif sourceType == "artist":
            #user_id = getUserId(source["value"])
            addPostsource2Dic(postSource, f"art/{source['value']}", sourceStr)

        elif sourceType == "project":
            addPostsource2Dic(postSource, f"pro/{source['value']}", sourceStr)
        else:
            pass #TODO: error logging
    return postSource

def getProjectsFromPostSource(source, cacheObj):
    '''input : 
        - source is the source identifier in the 'col/id' style
        - cacheobj is the tuple representation of the loaded cache file

    output : 
        is a list of list projectList[project entry][project info field]
    '''
    outProj = []
    splitedStr = source.split('/')
    srcType = splitedStr[0]
    srcValue =None
    if len(splitedStr) > 1:
        srcValue = splitedStr[1]

    if srcType == 'col':
        outProj = processCollections(srcValue,cacheObj)
    elif srcType == 'art':
        outProj = processArtist(srcValue,cacheObj)
    elif srcType == 'pro':
        if srcValue not in cacheObj[2]: #TODO :add more info as in processFunctions
            temp = ['']*len(cacheColumns)
            temp[0] = '0'
            temp[1] = srcValue
            temp[2] = [source]
            outProj.append(temp)
    elif srcType == 'lik':
        outProj = processLikes(srcValue,cacheObj)
    return outProj


def getNamingVariables(jsonObj, asset,project):
    minIdCategory = jsonObj["categories"][0]["id"]
    for cat in jsonObj["categories"]:
        if cat["id"] < minIdCategory:
            minIdCategory = cat["id"]
    variables = {
        "artist": jsonObj["user"]["username"],
        "title": jsonObj["title"] if len(jsonObj["title"].split(' ')) <= 4 else jsonObj["slug"],
        "subtitle": asset["title"] if asset["title"] is not None else "" ,
        "likes": str(jsonObj["likes_count"]),
        "source": "_".join(project[cacheColumns.index("protosources")]),
        "size": project[cacheColumns.index("default_size")],
        "subId" : str(asset["position"]),
        "category" : jsonObj[minIdCategory]["name"],
        "views_count": str(jsonObj["views_count"]),
        "comments_count": str(jsonObj["comments_count"]),
        "ext" : "jpg"
    }
    #TODO : edit cache values here for additionnal info
    return variables


def getUrlWithSize(url, size):
    return re.sub("/(small|medium|large|4k|small_square|micro_square|default)/",
        f"/{size}/",url)

def addImagesToList(imageList : list, jsonObj,projectIdx,projectObj, naming_convention = "{artist}_{title}_{source}"):
    #list of tuple (img name, img link, projectIdx)
    if len(jsonObj["assets"]) >1 and "{subId}" not in naming_convention:
        naming_convention = naming_convention + "{subId}.{ext}"
    else :
        naming_convention = naming_convention + ".{ext}"
    for asset in jsonObj["assets"]:
        if asset["asset_type"] != "video":
            availableVariables = getNamingVariables(jsonObj,asset,projectObj)
            imglink = asset["image_url"]
            imgName = naming_convention.format(**availableVariables)
            imageList.append( (imgName,imglink,projectIdx) )
    return imageList

def getProjectsIndexByStatus(cacheObj, status):
    return [elementIndex for elementIndex in range(len(cacheObj[0])) if cacheObj[0][elementIndex][0] == status]
# ------------ main cli functions

def logger(message,category):
    print(f"{category} : {message}")

def fetchCache(path,args=None,cache= None):
    pass
    #load lib
    libSettings = loadLibrarySettings(path)
    #load cache
    if cache is None:
        cacheObj = loadCacheFile(path)
    else:
        cacheObj = cache
    #get post sources
    postSources = getPostSource(libSettings["sources"])
    #foreach postsource get projects (merge post sources) ,stop when last page element is not in chache with same post source
    for source in postSources.keys():
        projects = getProjectsFromPostSource(source,cacheObj)
        for project in projects:
            project_id = project[1]
            if (project[0] == 2):
                cacheObj[0][getProjectIndexInCache(cacheObj,project_id)][cacheColumns.index("postsources")].append(source)
                for protoSource in postSources[source]:
                    if protoSource not in cacheObj[0][getProjectIndexInCache(cacheObj, project_id)][cacheColumns.index("protosources")]:
                        cacheObj[0][getProjectIndexInCache(cacheObj, project_id)][cacheColumns.index("protosources")].append(protoSource)
            else:
                project[cacheColumns.index("protosources")] = postSources[source]
                addProjectToCache(cacheObj,project)
    return cacheObj

def downloadPending(path,args=None,cache=None,preferedSize=None):
    #load lib
    libSettings = loadLibrarySettings(path)
    #load cache
    if cache is None:
        cacheObj = loadCacheFile(path)
    else :
        cacheObj = cache
    #get project not processed from cache
    projects = getProjectsIndexByStatus(cacheObj,0)
    #foreach not processed cache entry #cf requests-futures request & as_completed workflow
    session = FuturesSession()
    futures_requests = []
    for projectIdx in projects:
        #get config context 
        project = cacheObj[0][projectIdx]
        #sendRequest
        requestObj = getProjectDetailsRequest(session,project[1])
        requestObj.projectIdx = projectIdx
        futures_requests.append(requestObj)
    #process arrived requests
    images2BeDownloaded = [] #list of tuple (img name, img link, projectIdx)
    for requestObj in as_completed(futures_requests):
        response = requestObj.result()
        addImagesToList(images2BeDownloaded,
                response.json(),
                response.projectIdx,
                cacheObj[0][response.projectIdx],
                libSettings.get("namingConvention","{artist}_{title}_{source}")
                )

    futures_images = []
    for image in images2BeDownloaded:
        imgSize = preferedSize if preferedSize is not None else libSettings.get("default-size","large")
        imgLink = getUrlWithSize(image[1],imgSize)
        requestObj = session.get(imgLink)
        requestObj.imgName = image[0]
        requestObj.projectIdx = image[2]
        futures_images.append(requestObj)
    for requestObj in as_completed(futures_images):
        response = requestObj.result()
        #download image
        with open(os.path.join(path,requestObj.imgName),'wb') as imgfile:
            imgfile.write(response.content)
        #set processed (write over with all other info from request)
        cacheObj[0][response.projectIdx][cacheColumns.index("status")] = 1
    return cacheObj

def buildOverviewWebpage(path):
    pass

def buildColorPaletteWebPage(path):
    pass
# ------------ cli action
def exeCli(args):
    if args.action == 'createLib':
        config = loadLibrarySettings(os.path.dirname(__file__),'sample_libSettings.yaml')
        if args.src is not None:
            sources = config.get("sources",[])
            for src in args.src:
                sources.append({"type":src[0],"value":src[1]})
            config["sources"] = sources
        writeLibrarySettings(args.path,config)
    elif args.action == 'fetch':
        cache = ([],None,{}) if args.ignoreCache else None
        cache = fetchCache(args.path,args,cache= cache)
        if not args.dontUpdateCache:
            saveCacheFile(args.path,cache)
    elif args.action == 'pull':
        cache = ([], None, {}) if args.ignoreCache else None
        cache = downloadPending(args.path,args,cache=cache,preferedSize=args.default_size)
        if not args.dontUpdateCache:
            saveCacheFile(args.path, cache)
    elif args.action == 'update':
        cache = ([], None, {}) if args.ignoreCache else None
        cache = fetchCache(args.path, args, cache=cache)
        cache = downloadPending(
            args.path, args, cache=cache, preferedSize=args.default_size)
        if not args.dontUpdateCache:
            saveCacheFile(args.path, cache)
    elif args.action == 'write2lib':
        config = loadLibrarySettings(args.path, 'sample_libSettings.yaml')
        if args.src is not None:
            sources = config.get("sources", [])
            for src in args.src:
                sources.append({"type": src[0], "value": src[1]})
            config["sources"] = sources
        writeLibrarySettings(args.path, config)
        

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Maintain a image reference librairy from artstation')
    parser.add_argument("action", nargs=1, type=str,choices=['fetch','update','pull','creatLib','write2lib','help'],help='choose the specified action on the library',required=True)
    parser.add_argument(
        "--ignoreCache",action = "store_true", help="ignore the cache file during operations (for experienced user only)")
    parser.add_argument(
        "--dontUpdateCache", action="store_true", help="dont write to disk the cache file during operations (for experienced user only)")
    parser.add_argument("--path",type=str,default='.')
    parser.add_argument("--src",type=str,action="append",nargs=2,metavar=("srcType","value"),help="when in [createLib,write2lib] mode, specify what sources to write to lib config file")
    parser.add_argument("--default_size",type=str,choices=['small','medium','large','4k','small_square','micro_square'],nargs=1)
    args = parser.parse_args()
    if args.action == 'help':
        parser.print_help()
    exeCli(args)

    closePlaywrightPage()
