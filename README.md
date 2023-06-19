Submmision by:
1. Roee Milo - 319091690
2. Amit Butnik - 318988409

Configuration Details:

Default Region: us-east-1
Setup Script: setup.sh (compatible with Ubuntu OS)

Manager Nodes:
In order to utilize the Redis cluster, we have employed two environment variables. These variables are necessary for the smooth functioning of the cluster. The variable names are as follows:

localIP
maxWorkers
There is an additional environment variable that becomes relevant only if both servers are already operational.

Flask Output File:
The Flask output file can be found at the following location: /home/ubuntu/flask_output.log
On each machine, this file contains the detailed communication requests that have been sent to it. For example, if you are waiting to see a "pullcompleted" product, you need to monitor the manager's Flask output document, as it receives this request from the worker.

Potential Faults:
For a comprehensive understanding of potential faults, please refer to the information provided in the "potential-faults.txt" file.
