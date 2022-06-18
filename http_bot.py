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
import json
import sys
import time
import threading
import math
import configparser

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

numThreads=5
isRunThreads=True

def parseConfigs():
    parser = configparser.ConfigParser()
    parser.read("config.txt")
    global urlWebHost, linkLogin, linkCheckAccess, linkBookingToken, linkCheckAllow, linkQueueing, username, password, clientID
    urlWebHost = parser.get("DEFAULT", "urlWebHost")
    linkLogin = urlWebHost + "/" + parser.get("DEFAULT", "endpointLogin")
    linkCheckAccess = urlWebHost + "/" + parser.get("DEFAULT", "endpointCheckAccess")
    linkBookingToken = urlWebHost + "/" + parser.get("DEFAULT", "endpointBookingToken")
    linkCheckAllow = urlWebHost + "/" + parser.get("DEFAULT", "endpointCheckAllow")
    linkQueueing = parser.get("DEFAULT", "urlQueueing")
    username = parser.get("DEFAULT", "username")
    password = parser.get("DEFAULT", "password")
    clientID = parser.get("DEFAULT", "clientID")
    print("parseConfigs: urlWebHost:"+urlWebHost+"; linkLogin:"+linkLogin+"; linkCheckAccess:"+linkCheckAccess+";")
    print("parseConfigs: username:"+username+"; password:"+password+"; clientID:"+clientID+";")
    

def doLogin(isWriteToFile=False):
    #print("doLogin: START;")
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
    print("doCheckAccess: START")
    myPayload = {}
    myHeaders = {}
    myHeaders["access-token"] = accessToken
    myHeaders["content-type"] = "text/plain"
    respObj = doScraperWithExpectStatuses(linkCheckAccess, False, myPayload, myHeaders, expectStatusCodes=[200, 401])
    if respObj.status_code == 401:
        print("doCheckAccess: WARN: status code 401 is returned, need to re-login.")
        exit()
    if isWriteToFile:
        writeResponseToFile(respObj, "check_access")

def doGetBookingToken(accessToken, isWriteToFile=False):
    print("doGetBookingToken: START")
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
    #print("doGetAllowAssign: START")
    myPayload = {}
    myHeaders = {}
    myHeaders["access-token"] = accessToken
    respObj = doScraperWithExpectStatuses(linkCheckAllow, True, myPayload, myHeaders, expectStatusCodes=[200, 409])
    if isWriteToFile:
        writeResponseToFile(respObj, "allow_assign")

def doQueueing(bookingToken, isWriteToFile=False):
    #print("doQueueing: START")
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
        print("doQueueing: vb is None;")
    elif int(va) == 0:
        numPeopleAhead = 0
    elif int(vb) > 0:
        numPeopleAhead = int(va) / int(vb)
    if isWriteToFile:
        writeResponseToFile(respObj, "queueing")
    return math.ceil(numPeopleAhead)

def doScraperWithExpectStatuses(aLink, isGet, aPayload, aHeaders, expectStatusCodes=[0]):
    print("doScraperWithExpectStatuses: aLink:"+aLink+"; expectStatusCodes:"+str(expectStatusCodes)+";")
    isExpectedStatusCode = False
    while not isExpectedStatusCode:
        scraper = cloudscraper.create_scraper()  
        if isGet:
            responseObj = scraper.get(aLink, headers=aHeaders)
        else:
            responseObj = scraper.post(aLink, json=aPayload, headers=aHeaders)
        statusCode = responseObj.status_code
        print("doScraperWithExpectStatuses: scraper got response, statusCode:"+str(statusCode)+";")
        if 0 in expectStatusCodes:
            isExpectedStatusCode = True
        else:
            isExpectedStatusCode = statusCode in expectStatusCodes
    return responseObj
    
def writeResponseToFile(responseObj, suffix):
    filename="resp-" + suffix + "-" + str(responseObj.status_code) + ".json"
    print("writeResponseToFile: filename:" + filename + "; length:" + str(len(responseObj.text)) + ";");
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
        print("queueThread.run: Starting " + self.name)
        if self.mode == "queue":
            pollQueue(self.name, self.accessToken, self.bookingToken, self.delay)
        elif self.mode == "keepalive":
            keepAlive(self.name, self.accessToken, self.bookingToken, self.delay)
        else:
            print("queueThread.run: ERROR - unknown mode:" + self.mode + ";")
        print("queueThread.run: Exiting " + self.name)

def keepAlive(threadName, aToken, bToken, delay):
    while True:
        doCheckAccess(accessToken, False)
        #doGetAllowAssign(accessToken, True)
        print("keepAlive: [" + time.ctime(time.time()) + "]-[" + threadName + "];")
        if delay > 0:
            time.sleep(delay)


def pollQueue(threadName, aToken, bToken, delay):
    global isRunThreads
    while isRunThreads:
        numPeopleAhead=doQueueing(bToken, True)
        print("pollQueue: [" + time.ctime(time.time()) + "]-[" + threadName + "]; numPeopleAhead:" + str(numPeopleAhead) + ";")
        if numPeopleAhead != 99999999:
            isRunThreads = False
        if delay > 0:
            time.sleep(delay)

def runQueueThreads(numThreads, accessToken, bookingToken, delay, mode):
    print("runQueueThreads: START; numThreads:" + str(numThreads) + ";")
    qThreads=[]
    for i in range(numThreads):
        aQThread = queueThread(i, "qTh-"+str(i), accessToken, bookingToken, delay, mode)
        qThreads.append(aQThread)
    for i in range(numThreads):
        qThreads[i].start()
    print("runQueueThreads: END;")


print("http_bot: START; v1.10;")
parseConfigs()
accessToken = doLogin(True)
print("http_bot: after doLogin(); accessToken:"+accessToken+";")

doCheckAccess(accessToken, True)
#print("http_bot: after doCheckAccess();")

bookingToken = doGetBookingToken(accessToken, isWriteToFile=True)
print("http_bot: after doGetBookingToken(); bookingToken:"+bookingToken+";")

#numPeopleAhead = doQueueing(bookingToken, True)
#print("http_bot: after doQueueing; numPeopleAhead:"+str(numPeopleAhead)+";")

#doGetAllowAssign(accessToken, True)

runQueueThreads(numThreads, accessToken, bookingToken, 0, "queue")
#runQueueThreads(numThreads, accessToken, bookingToken, 5, "keepalive")

print("http_bot: END")