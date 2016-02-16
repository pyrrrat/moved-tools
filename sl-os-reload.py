# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import fnmatch
import sys
import time

import SoftLayer

parser = argparse.ArgumentParser(description='Reload and wait for SL hosts')

parser.add_argument('-y', '--yes',
                    action='store_true',
                    help="Don't prompt. Assume yes")

parser.add_argument('hosts',
                    metavar='HOST',
                    nargs='+',
                    help='host names to reload')

opts = parser.parse_args()

hosts = opts.hosts

client = SoftLayer.create_client_from_env()

vs = SoftLayer.VSManager(client)
ssh = SoftLayer.SshKeyManager(client)
hardware = SoftLayer.HardwareManager(client)

instances = []

for i in vs.list_instances() + hardware.list_hardware():
    for pattern in hosts:
        if fnmatch.fnmatchcase(i['fullyQualifiedDomainName'], pattern):
            instances.append(i)
            break

if not opts.yes:
    names = [" - %s" % i['fullyQualifiedDomainName'] for i in instances]
    names = "\n".join(sorted(names))
    prompt = raw_input("Going to reload:\n%s\nStart [y/N]: " % names)

    if prompt.lower() not in ('y', 'yes'):
        sys.exit(0)

transactions = []

for instance in instances:
    try:
        transactions.append((instance['fullyQualifiedDomainName'],
                             instance['activeTransaction']))
    except KeyError:
        pass

if transactions:
    msgs = ["%s: %s" % (n, t['transactionStatus']['name'])
            for n, t in transactions]
    print("Aborting due to active transactions in target list:\n%s" %
          "\n".join(msgs))
    sys.exit(1)

# install all the ssh keys we can find
ssh_keys = [key['id'] for key in ssh.list_keys()]

for instance in instances:
    fqdn = instance['fullyQualifiedDomainName']
    try:
        if instance.get('hardwareStatusId'):
            hardware.reload(instance['id'], ssh_keys=ssh_keys)
        else:
            vs.reload_instance(instance['id'], ssh_keys=ssh_keys)
    except SoftLayer.exceptions.SoftLayerAPIError as e:
        print("Failed to reload %s due to %s" % (fqdn, e))
    else:
        print("Reloaded %s" % fqdn)

# wait for them to reload
instance_names = [i['fullyQualifiedDomainName'] for i in instances]

while True:
    all_waiting = vs.list_instances() + hardware.list_hardware()

    waiting = [i.get('activeTransaction') for i in all_waiting
               if i['fullyQualifiedDomainName'] in instance_names]

    if not any(waiting):
        break

    sys.stdout.write(".")
    sys.stdout.flush()
    time.sleep(5)

sys.stdout.write("\n")
