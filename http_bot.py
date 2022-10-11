"""
Copyright 2022 Philip C Kwan

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Name of program: http_bot.py
Author: Philip Kwan (philipckwan@gmail.com)
First Released Date: 10-6-2022 (v1.10)
license: MIT License (https://opensource.org/licenses/MIT)

This program is an automation tool (a bot) to make HTTP requests following a specific flow.
One use of this tool is to obtain a booking token and queue in an online platform.
It simulates a human user using an internet browser to login to the website, go to a certain page, and click some buttons in order to queue for making bookings.
This program runs based on Python version 3 (i.e. Python v3.7.9). 

This program depends on several third party libraries, in which it has no guarantees that it can continue to work with any newer versions.
-cloudscraper (https://pypi.org/project/cloudscraper/) for bypassing Cloudflare bot challanges
-python threading module, for firing multiple threads in order to get ahead in the queue

"""

import cloudscraper
import time
import threading
import math
import configparser
from datetime import datetime
import logging
import os.path

#hostURL=
urlWebHost=""
linkLogin=""
linkCheckAccess=""
linkBookingToken=""
linkCheckAllow=""
linkQueueing=""

username=""
password=""
clientID=""
accessTokenOverride=""
bookingTokenOverride=""
scheduleRunTime=None

numThreads=1
numMaxTrials=20
isRunThreads=True
isRunThreadOnce=True

myLog = logging.getLogger("myLogger") 
formatter = logging.Formatter("[%(asctime)s.%(msecs)03d]-%(message)s","%Y-%m-%d %H:%M:%S")
hdlr = logging.StreamHandler()
hdlr.setFormatter(formatter)
now = datetime.now()
nowStr = now.strftime("%Y%m%d-%H%M%S")
logDirname = "logs"
if not os.path.exists(logDirname):
    os.makedirs(logDirname)
logFilename = logDirname + "/log-" + nowStr+ ".txt"

fhdlr = logging.FileHandler(logFilename)
fhdlr.setFormatter(formatter)
myLog.addHandler(hdlr)
myLog.addHandler(fhdlr)
myLog.setLevel(logging.DEBUG)

def log(msg):
    myLog.debug(msg)

def parseConfigs():
    parser = configparser.ConfigParser()
    parser.read("config.txt")
    global urlWebHost, linkLogin, linkCheckAccess, linkBookingToken, linkCheckAllow, linkQueueing, username, password, clientID, accessTokenOverride, bookingTokenOverride, scheduleRunTime, numThreads
    urlWebHost = parser.get("DEFAULT", "urlWebHost")
    linkLogin = urlWebHost + "/" + parser.get("DEFAULT", "endpointLogin")
    linkCheckAccess = urlWebHost + "/" + parser.get("DEFAULT", "endpointCheckAccess")
    linkBookingToken = urlWebHost + "/" + parser.get("DEFAULT", "endpointBookingToken")
    linkCheckAllow = urlWebHost + "/" + parser.get("DEFAULT", "endpointCheckAllow")
    linkQueueing = parser.get("DEFAULT", "urlQueueing")
    username = parser.get("DEFAULT", "username")
    password = parser.get("DEFAULT", "password")
    clientID = parser.get("DEFAULT", "clientID")
    numThreads = int(parser.get("DEFAULT", "numThreads"))
    accessTokenOverride = parser.get("DEFAULT", "accessTokenOverride", fallback="none")
    bookingTokenOverride = parser.get("DEFAULT", "bookingTokenOverride", fallback="none")
    scheduleRunTimeStr = parser.get("DEFAULT", "scheduleRunTime", fallback="none")
    log("parseConfigs: urlWebHost:"+urlWebHost+"; linkLogin:"+linkLogin+"; linkCheckAccess:"+linkCheckAccess+";")
    log("parseConfigs: username:"+username+"; password:"+password+"; clientID:"+clientID+";")
    log("parseConfigs: accessTokenOverride:"+accessTokenOverride+";")
    log("parseConfigs: bookingTokenOverride:"+bookingTokenOverride+";")
    log("parseConfigs: scheduleRunTimeStr:"+scheduleRunTimeStr+";")
    log("parseConfigs: numThreads:"+str(numThreads)+";")

    scheduleRunTime=datetime.now()
    try:
        strSplit=scheduleRunTimeStr.split(":")
        scheduleHour=int(strSplit[0]);
        scheduleMinute=int(strSplit[1]);
        strSecondAndMillisecond = strSplit[2]
        strSplit=strSecondAndMillisecond.split(".")
        scheduleSecond=int(strSplit[0]);
        scheduleMicrosecond = 550000
        if len(strSplit) > 1: 
            scheduleMillisecond=int(strSplit[1])
            scheduleMicrosecond=scheduleMillisecond * 1000
        scheduleRunTime=datetime.now().replace(hour=scheduleHour, minute=scheduleMinute, second=scheduleSecond, microsecond=scheduleMicrosecond)
    except:
        log("parseConfigs: WARN - invalid time input for scheduleRunTime, default to now.")

def doLogin(isWriteToFile=False):
    if accessTokenOverride and len(accessTokenOverride) > 5:
        log("doLogin: accessTokenOverride is set, will skip this action;")
        return accessTokenOverride
    myPayload = {}
    myPayload["username"] = username
    myPayload["password"] = password
    myPayload["db"] = "devel"
    myPayload["replace_session"] = "true"
    myHeaders = {}
    myHeaders["content-type"] = "text/plain"
    respObj = doScraperWithExpectStatuses(linkLogin, False, myPayload, myHeaders, [200])
    respJson = respObj.json()
    accessToken = respJson.get("access_token")
    if isWriteToFile:
        writeResponseToFile(respObj, "get_tokens")
    return accessToken

def doCheckAccess(accessToken, isWriteToFile=False):
    log("doCheckAccess: START")
    myPayload = {}
    myHeaders = {}
    myHeaders["access-token"] = accessToken
    myHeaders["content-type"] = "text/plain"
    respObj = doScraperWithExpectStatuses(linkCheckAccess, False, myPayload, myHeaders, expectStatusCodes=[200, 401])
    if respObj.status_code == 401:
        log("doCheckAccess: WARN: status code 401 is returned, need to re-login.")
        exit()
    if isWriteToFile:
        writeResponseToFile(respObj, "check_access")

def doGetBookingToken(accessToken, isWriteToFile=False):
    #log("doGetBookingToken: START")
    if bookingTokenOverride and len(bookingTokenOverride) > 10:
        log("doGetBookingToken: bookingTokenOverride is set, will skip this action;")
        return bookingTokenOverride
    myPayload = {}
    myHeaders = {}
    myHeaders["access-token"] = accessToken
    respObj = doScraperWithExpectStatuses(linkBookingToken, True, myPayload, myHeaders, expectStatusCodes=[200])
    respJson = respObj.json()
    bookingToken = respJson.get("booking_token")
    if isWriteToFile:
        writeResponseToFile(respObj, "bookingToken")
    return bookingToken

def doGetAllowAssign(accessToken, isWriteToFile=False):
    #log("doGetAllowAssign: START")
    myPayload = {}
    myHeaders = {}
    myHeaders["access-token"] = accessToken
    respObj = doScraperWithExpectStatuses(linkCheckAllow, True, myPayload, myHeaders, expectStatusCodes=[200, 409])
    if isWriteToFile:
        writeResponseToFile(respObj, "allow_assign")

def doQueueing(bookingToken, isWriteToFile=False):
    #log("doQueueing: START")
    myPayload = {}
    myPayload["action"] = "beep"
    myPayload["client_id"] = clientID
    myPayload["id"] = bookingToken
    myHeaders = {}
    respObj = doScraperWithExpectStatuses(linkQueueing, False, myPayload, myHeaders, expectStatusCodes=[200])
    respJson = respObj.json()
    va = respJson.get("va")
    vb = respJson.get("vb")
    numPeopleAhead=99999999
    if vb is None:
        log("doQueueing: vb is None;")
    elif int(va) == 0:
        numPeopleAhead = 0
    elif int(vb) > 0:
        numPeopleAhead = int(va) / int(vb)
    if isWriteToFile:
        writeResponseToFile(respObj, "queueing")
    return math.ceil(numPeopleAhead)

def doScraperWithExpectStatuses(aLink, isGet, aPayload, aHeaders, expectStatusCodes=[0]):
    #log("doScraperWithExpectStatuses: aLink:"+aLink+"; expectStatusCodes:"+str(expectStatusCodes)+";")
    isExpectedStatusCode = False
    numTrials=0
    while not isExpectedStatusCode:
        scraper = cloudscraper.create_scraper()  
        if isGet:
            responseObj = scraper.get(aLink, headers=aHeaders)
        else:
            responseObj = scraper.post(aLink, json=aPayload, headers=aHeaders)
        numTrials = numTrials + 1
        statusCode = responseObj.status_code
        #log("doScraperWithExpectStatuses: scraper got response, statusCode:"+str(statusCode)+"; numTrials:" + str(numTrials) + ";")
        if numTrials >= numMaxTrials:
            log("doScraperWithExpectStatuses: numTrials exceeds numMaxTrials, giving up...")
            exit()
        if 0 in expectStatusCodes:
            isExpectedStatusCode = True
        else:
            isExpectedStatusCode = statusCode in expectStatusCodes
    return responseObj
    
def writeResponseToFile(responseObj, suffix):
    filename="resp-" + suffix + "-" + str(responseObj.status_code) + ".json"
    log("writeResponseToFile: filename:" + filename + "; length:" + str(len(responseObj.text)) + ";");
    f = open(filename, "w")
    f.write(responseObj.text)
    f.close()
    
class queueThread(threading.Thread):
    def __init__(self, threadID, name, accessToken, bookingToken, delay, mode):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.accessToken = accessToken
        self.bookingToken = bookingToken
        self.delay = delay
        self.mode = mode

    def run(self):
        log("queueThread.run: Starting [" + self.name + "]")
        if self.mode == "queue":
            pollQueue(self.name, self.accessToken, self.bookingToken, self.delay)
        elif self.mode == "keepalive":
            keepAlive(self.name, self.accessToken, self.bookingToken, self.delay)
        else:
            log("queueThread.run: ERROR - unknown mode:" + self.mode + ";")
        log("queueThread.run: Exiting " + self.name)

class queueThreadOnce(threading.Thread):
    def __init__(self, threadID, bookingToken):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.bookingToken = bookingToken
        
    def run(self):
        global isRunThreadOnce
        log("queueThreadOnce.run:[" + str(self.threadID) + "]; starting;")
        numPeopleAhead=doQueueing(self.bookingToken, False)
        log("queueThreadOnce.run:[" + str(self.threadID) + "]; numPeopleAhead:" + str(numPeopleAhead) + ";")
        if numPeopleAhead != 99999999:
            isRunThreadOnce = False

def keepAlive(threadName, aToken, bToken, delay):
    while True:
        doCheckAccess(aToken, False)
        #doGetAllowAssign(accessToken, True)
        log("keepAlive:[" + threadName + "];")
        if delay > 0:
            time.sleep(delay)


def pollQueue(threadName, aToken, bToken, delay):
    global isRunThreads
    while isRunThreads:
        numPeopleAhead=doQueueing(bToken, False)
        log("pollQueue:[" + threadName + "]; numPeopleAhead:" + str(numPeopleAhead) + ";")
        if numPeopleAhead != 99999999:
            isRunThreads = False
        if delay > 0:
            time.sleep(delay)

def runQueueThreads(numThreads, accessToken, bookingToken, delay, mode):
    log("runQueueThreads: START; numThreads:" + str(numThreads) + ";")
    qThreads=[]
    for i in range(numThreads):
        aQThread = queueThread(i, "qTh-"+str(i), accessToken, bookingToken, delay, mode)
        qThreads.append(aQThread)
    for i in range(numThreads):
        qThreads[i].start()
    log("runQueueThreads: END;")

def runUnlimitedQueueThreadOnce(bookingToken):
    # run unlimited number of queueThreadOnce
    # each queueThreadOnce only queue once
    # stop until a queueThreadOnce able to queue
    log("runUnlimitedQueueThreadOnce: START;")
    count = 0
    while isRunThreadOnce:
        count = count + 1
        aQThreadOnce = queueThreadOnce(count, bookingToken)
        aQThreadOnce.start()
    log("runUnlimitedQueueThreadOnce: END;")

def waitTillScheduledTimeBeforeContinue():
    while datetime.now() < scheduleRunTime:
        log("waitTillScheduledTimeAndQueue: current time:[" + str(datetime.now())[:-3] + "]; scheduled time:[" + str(scheduleRunTime)[:-3] + "], still waiting...")
        time.sleep(0.1)
    log("waitTillScheduledTimeAndQueue: current time:[" + str(datetime.now())[:-3] + "]; scheduled time:[" + str(scheduleRunTime)[:-3] + "], will continue the rest of program")
    

log("http_bot: START; v1.12;")
parseConfigs()

accessToken = doLogin(True)
log("http_bot: after doLogin(); accessToken:"+accessToken+";")

bookingToken = doGetBookingToken(accessToken, isWriteToFile=True)
log("http_bot: after doGetBookingToken(); bookingToken:"+bookingToken+";")

numPeopleAhead = doQueueing(bookingToken, True)
log("http_bot: after doQueueing; numPeopleAhead:"+str(numPeopleAhead)+";")

waitTillScheduledTimeBeforeContinue()

if numThreads > 0:
    runQueueThreads(numThreads, accessToken, bookingToken, 0, "queue")
else:
    runUnlimitedQueueThreadOnce(bookingToken)

log("http_bot: END")