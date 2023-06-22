import os
import hashlib
import base64
import json
import requests
import threading
import time
import subprocess
from flask import Flask,request,Response, jsonify
from datetime import datetime

class Worker:
    # ec2 - terminate on shutdown

    FirstManager = None
    SecondManager = None
    LastManager = None
    instanceID = None

    def __init__(self, id, FirstManager):
        self.FirstManager = FirstManager
        self.instanceID = id

    def do_work(self,buffer, iter_num):
        result = hashlib.sha512(buffer).digest()
        for res in range(iter_num - 1):
            result = hashlib.sha512(result).digest()
        return result

    def workerDone(self):
        subprocess.run(["aws", "ec2", "terminate-instances", "--instance-ids", self.instanceID])
        if self.FirstManager:
            url = f"http://{self.FirstManager}:5000/workerIsDone"
            requests.get(url)


    def update_IP(self, ip, is_first):
        if is_first:
            self.FirstManager = ip
        else:
            self.SecondManager = ip

    def processWorkById(self, work, manager_ip, workID):
        buffer = base64.b64decode(work.json()['buffer'])
        iterations = int(work.json()['iterations'])
        hash = self.do_work(buffer,iterations)
        url2 = f"http://{manager_ip}:5000/workIsCompleted?workID={workID}&bufferHash={hash}"

        requests.get(url2)
        lastTime = datetime.now()
    ##runs until a maximum time limit is reached.
    ##checks for work from two IP addresses and performs the work if available, notifying the completion
    def loop(self):
        max = 240
        timeToSleep = 80
        lastTime = datetime.now()
        d = 0
        while d <= max:
            nodes = [self.FirstManager, self.SecondManager]
            for manager_ip in nodes:
                if manager_ip:
                    url1 = f"http://{manager_ip}:5000/getWork"
                    work = requests.get(url1)
                    workID = work.json()['workID']
                    if workID:
                        self.processWorkById(work, manager_ip, workID)
                        if workID:
                            continue
            time.sleep(timeToSleep)
            d = (datetime.now() - lastTime).total_seconds()
        self.workerDone()


app = Flask(__name__)

variables = {}
with open("workerVariables.txt", "r") as file:
    for line in file:
        key, value = line.strip().split("=")
        variables[key] = value

instanceID = variables['instanceID']
primaryIP = variables['primaryIP']
secondaryIP = None

worker = Worker(instanceID, primaryIP)
def workerLoop():
    worker.loop()
    
timer_thread = threading.Thread(target=workerLoop)
timer_thread.daemon = True
timer_thread.start()


def run_process():
    scode = 200

    if worker.FirstManager:
        runWorker(scode, True)

    if worker.SecondManager:
        runWorker(scode, False)



def runWorker(scode,isFirst):
    if isFirst:
        url = f"http://{worker.FirstManager}:5000/getSecondaryIP"
    else:
        url = f"http://{worker.SecondManager}:5000/getSecondaryIP"
    response = requests.get(url)
    if response.status_code == scode:
        secondaryIP = response.json()['secondaryIP']
        worker.update_IP(secondaryIP, not isFirst)
    else:
        worker.update_IP(None, isFirst)


run_process
