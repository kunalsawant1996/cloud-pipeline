# Copyright 2017-2019 EPAM Systems, Inc. (https://www.epam.com/)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pipeline import Logger, TaskStatus, PipelineAPI, StatusEntry
from pipeline import Kubernetes
import argparse
import os
import subprocess
import time

class Task:

    def __init__(self):
        self.task_name = 'Task'

    def fail_task(self, message):
        error_text = '{} task failed: {}.'.format(self.task_name, message)
        Logger.fail(error_text, task_name=self.task_name)
        raise RuntimeError(error_text)

class MasterNode(Task):

    def __init__(self):
        Task.__init__(self)
        self.task_name = 'WaitForMasterNode'
        self.kube = Kubernetes()
        self.pipe_api = PipelineAPI(os.environ['API'], 'logs')

    def await_master_start(self, master_id, task_name):
        try:
            Logger.info('Waiting for master node (run id: {}), task: {}'.format(master_id, task_name), task_name=self.task_name)

            # approximately 1 day. we really do not need this timeout, as if something will go wrong with a master - workers will be killed automatically
            # but for any unpredictable case - this task will be killed eventually
            attempts = 8640
            master = None
            Logger.info('Waiting for master node ...', task_name=self.task_name)
            while not master and attempts > 0:
                master = self.get_master_node_info(master_id, task_name)
                attempts -= 1
                time.sleep(10)
            if not master:
                raise RuntimeError('Failed to attach to master node')

            Logger.success('Attached to master node (run id {})'.format(master_id), task_name=self.task_name)
            return master
        except Exception as e:
            self.fail_task(e.message)

    def get_master_node_info(self, master_id, task_name):
        pod = self.kube.get_pod(master_id)
        if pod and pod.status == 'Running':
            task_logs = self.pipe_api.load_task(master_id, task_name)
            if not task_logs:
                return None
            task_status = task_logs[-1]['status']
            if task_status == 'SUCCESS':
                return pod
            elif task_status != 'RUNNING':
                raise RuntimeError('Worker failed to start as it cannot attach to master node (run id {})'.format(master_id))
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--master-id', type=int, required=True)
    parser.add_argument('--task-name', required=True)
    args = parser.parse_args()
    run_id = os.environ['RUN_ID']

    status = StatusEntry(TaskStatus.SUCCESS)
    workers = []
    try:
        master = MasterNode().await_master_start(args.master_id, args.task_name)
        print(master.name + " " + master.ip)
        exit(0)
    except Exception as e:
        Logger.warn(e.message)
        status = StatusEntry(TaskStatus.FAILURE)
    if status.status == TaskStatus.FAILURE:
        raise RuntimeError('Failed to setup cluster')

    
    
if __name__ == '__main__':
    main()
