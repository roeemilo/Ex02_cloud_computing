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

    def __init__(self, id, FirstManager, SecondManager):
        self.FirstManager = FirstManager
        self.SecondManager = SecondManager
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

    ##runs until a maximum time limit is reached.
    ##checks for work from two IP addresses and performs the work if available, notifying the completion
    def loop(self):
        max = 240
        scode = 200
        timeToSleep = 60
        lastTime = datetime.now()
        d = 0
        while d <= max:
            nodes = [self.FirstManager, self.SecondManager]
            for manager_ip in nodes:
                if manager_ip:
                    url1 = f"http://{manager_ip}:5000/getWork"
                    work = requests.get(url1)
                    if work.status_code == scode:
                        workID = work.json()['workID']
                        if workID:
                            buffer = base64.b64decode(work.json()['buffer'])
                            iterations = int(work.json()['iterations'])
                            hash = self.do_work(buffer,iterations)
                            url2 = f"http://{manager_ip}:5000/workIsCompleted?workID={workID}&bufferHash={hash}"
                            requests.get(url2)
                            lastTime = datetime.now()
                            if workID:
                                continue
            time.sleep(timeToSleep)
            d = (datetime.now() - lastTime).total_seconds()
        self.workerDone()


app = Flask(__name__)

instanceID = os.environ.get('instanceID')
primaryIP = os.environ.get('primaryIP')
secondaryIP = os.environ.get('secondaryIP')
worker = Worker(instanceID, primaryIP, secondaryIP)
def workerLoop():
    worker.loop()
    
timer_thread = threading.Thread(target=workerLoop)
timer_thread.daemon = True
timer_thread.start()


def run_process():
    scode = 200
    time_to_sleep = 60

    while True:
        if worker.FirstManager:
            url1 = f"http://{worker.FirstManager}:5000/getOtherIP"
            response = requests.get(url1)
            if response.status_code == scode:
                otherIP = response.json()['otherIP']
                worker.update_IP(otherIP, False)
            else:
                worker.update_IP(None, True)

        if worker.SecondManager:
            url2 = f"http://{worker.SecondManager}:5000/getOtherIP"
            response = requests.get(url2)
            if response.status_code != scode:
                worker.update_IP(None, False)
            else:
                otherIP = response.json()['otherIP']
                worker.update_IP(otherIP, True)
        time.sleep(time_to_sleep)


timer_thread = threading.Thread(target=run_process)
timer_thread.daemon = True
timer_thread.start()