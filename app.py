import base64
import json
import os
import threading
import subprocess
import time
import requests
from datetime import datetime
from collections import deque
from flask import Flask,request,Response, jsonify

class EndpointNode:

    minNumWork = 0
    maxNumWork = 0
    numOfWorkers = 0
    startIP = None
    endIP = None
    otherIP = None
    workData = []
    workComplete = []


    def __init__(self, begin, endIP, otherIP) -> None:
        self.maxNumWork = begin
        self.minNumWork = begin
        self.endIP = endIP
        self.startIP = otherIP
        self.otherIP = otherIP

        if otherIP:
            try:
                url = f'http://{self.otherIP}:5000/OtherIPupdate?otherIP={self.endIP}'
                query1 = ""
                response = requests.get(url)
            except requests.exceptions.RequestException as error:
                self.otherIP = None

    def pullComplete(self, pick):
        if pick is None:
            return []
        else:
            scode = 200
            results = self.retrieveWorkItems(pick)
            if len(results) >= pick and pick is not None:
                return results
            if self.otherIP:
                try:
                    curr = pick - len(results)
                    url = f'http://{self.otherIP}:5000/retrieveWorkItems?pick={curr}'
                    response = requests.get(url)
                    if response.status_code == scode:
                        other_results = response.json()
                        res = results + other_results
                        return res
                except requests.exceptions.RequestException as error:
                    self.otherIP = None
                    self.startIP = None
            return results

    def retrieveWorkItems(self,pick):
        newpick = min(len(self.workComplete), pick)
        results = []
        for i in range(newpick):
            j = - (i + 1)
            results.append(self.workComplete[j])
        return results

    ##Checks if a certain amount of time has passed since a specific start time
    ##either spawns a worker if the conditions are met
    ##or interacts with another IP address to potentially spawn a worker.
    def timer_10_sec(self):
        if self.workData:
            start = self.workData[0][2]
            d = (datetime.now() - start).total_seconds()
            min = 15
            scode = 200
            query1 = ""

            if d > min:

                if self.numOfWorkers < self.maxNumWork and self.spawnWorker():
                    self.numOfWorkers += 1
                else:
                    if self.otherIP:
                        self.minNumWork -= 1
                        try:
                            url1 = f'http://{self.otherIP}:5000/getNodeQuota'
                            response = requests.get(url1)
                            if response.status_code == scode:
                                result = response.json()['result']
                                res_copy = result
                                if res_copy == "True":
                                    url2 = f'http://{self.otherIP}:5000/spawnWorker'
                                    response = requests.get(url2)
                        except requests.exceptions.RequestException as error:
                            self.otherIP = None
                            self.startIP = None


    def TryGetNodeQuota(self):
        ifThereIsSpace = False
        if self.numOfWorkers < self.maxNumWork:
            ifThereIsSpace = True
        return ifThereIsSpace


    def enqueueWork(self, buffer, iter_num, ID):
        self.workData.append((buffer, iter_num, datetime.now(), ID))


    def giveMeWork(self):
        try:
            worker = self.workData.pop(0)
            return worker
        except IndexError:
            return None


    def finish_work(self, key, ID):
        self.workComplete.append((key, ID))

################

    import subprocess

    def workerDone(self):
        self.minNumWork += 1
        self.numOfWorkers -= 1

    def updateTheManager(self, ip):
        self.otherIP = ip

    def spawnWorker(self):
        instanceID = None
        result = subprocess.run(['bash', '/home/ubuntu/workerSetup.sh'], capture_output=True, text=True)
        if result.returncode != 0:
            error = f"Script failed with error: {result.stderr}"
            print(error)
        else:
            instanceID = result.stdout.strip()

        if instanceID is None:
            return False
        else:
            return True


app = Flask(__name__)

variables = {}
with open("variables.txt", "r") as file:
    for line in file:
        key, value = line.strip().split("=")
        variables[key] = value



localIP = variables['localIP']
maxWorkers = int(variables['maxWorkers'])
otherIP = variables['otherIP']

workpick = 100
workNum = 0
workID = ''
Manager = EndpointNode(maxWorkers, localIP, otherIP)


##Manager_Manager
@app.route('/spawnWorker', methods=["GET"])
def spawnWorker():
    Manager.spawnWorker()
    res = Response(response='', status=200, mimetype='application/json')
    return res

@app.route('/getNodeQuota', methods=["GET"])
def getNodeQouta():
    res = Response(response=json.dumps({'result': Manager.TryGetNodeQuota()}), status=200, mimetype='application/json')
    return res

@app.route('/OtherIPupdate', methods=["GET"])
def OtherIPupdate():
    working = "OK"
    otherIP = request.args.get('otherIP')
    Manager.updateTheManager(otherIP)
    return working

@app.route('/retrieveWorkItems', methods=["GET"])
def retrieveWorkItems():
    pick = int(request.args.get('pick'))
    result = Manager.retrieveWorkItems(pick)
    json_data = jsonify(result)
    res = Response(response=json_data.data, status=200, mimetype='application/json')
    return res

##client_Manager
@app.route('/enqueue', methods=["PUT"])
def enqueueWork():
    global workID
    global secondWorkID
    global workNum
    global localIP
    iter = request.args.get('iterations')
    buffer = request.data
    workNum = 1 + workNum
    uWorkID = f"{id(workNum)}"
    Manager.enqueueWork(buffer, iter, uWorkID)
    res = Response(response=json.dumps({'WorkID': uWorkID}), status=200, mimetype='application/json')
    return res

@app.route('/pullCompleted', methods=["POST"])
def pullCompleted():
    top = int(request.args.get('top'))
    result = Manager.pullComplete(top)
    json_data = jsonify(result)
    res = Response(response=json_data.data, status=200, mimetype='application/json')
    return res

#worker_Manager
@app.route('/getWork', methods=["GET"])
def getWork():
    is_work = Manager.giveMeWork()
    if is_work:
        buffer_base64 = base64.b64encode(is_work[0]).decode()
        res = Response(response=json.dumps({'workID': is_work[3], 'buffer': buffer_base64, 'iterations': is_work[1]}), status=200, mimetype='application/json')
    else:
        res = Response(response=json.dumps({'workID': None}), status=200, mimetype='application/json')
    return res

@app.route('/workIsCompleted', methods=["GET"])
def workIsCompleted():
    workID = request.args.get('workID')
    bufferHash = request.args.get('bufferHash')
    Manager.finish_work(bufferHash, workID)
    res = Response(response='', status=200, mimetype='application/json')
    return res

@app.route('/workerIsDone', methods=["GET"])
def workerDone():
    Manager.workerDone()
    res = Response(response='', status=200, mimetype='application/json')
    return res


@app.route('/getOtherIP', methods=["GET"])
def getOtherIP():
    res = Response(response=json.dumps({'otherIP': Manager.otherIP}), status=200, mimetype='application/json')
    return res



def run_process():
    while True:
        Manager.timer_10_sec()
        time.sleep(10)

timer_thread = threading.Thread(target=run_process)
timer_thread.daemon = True
timer_thread.start()