# Python Azure Function to support HA for NVAs (designed for Meraki VMx)
# https://learn.microsoft.com/en-us/python/api/
#
import logging
import os
import socket
import time
from datetime import datetime, timezone

from azure.functions import TimerRequest
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network.models import Route, RouteNextHopType

# Checks a specified VM status
def test_vm_status(vm, fw_resource_group):
    vm_status = compute_client.virtual_machines.get(fw_resource_group, vm, expand="instanceView")
    statuses = vm_status.instance_view.statuses
    for status in statuses:
        if status.code == 'PowerState/running':
            return False
    return True

# Checks for a response on TCP port
def test_tcp_port(server, port):
    try:
        socket.create_connection((server, port), timeout=1)
        return True
    except (socket.timeout, ConnectionRefusedError):
        return False

# Failover from primary to secondary
def start_failover():
    # Get the tag value from the environment variable
    tag_value = os.environ['FWUDRTAG']

    # List resources with the specified tag
    resources = resource_client.resources.list(filter=f"tagName eq 'nva_ha_udr' and tagValue eq '{tag_value}'")

    for resource in resources:
        logging.info("Contents of resource: %s", resource)

        resource_group_name = resource.id.split('/')[4]

        logging.info("Resource group for %s is %s", resource.name, resource_group_name)

        # Get the route table for the resource
        route_table = network_client.route_tables.get(resource_group_name=resource_group_name, route_table_name=resource.name)

        for route in route_table.routes:
            logging.info("Updating %s route %s", route_table.name, route)

            for i in range(len(primary_ints)):
                if route.next_hop_ip_address == secondary_ints[i]:
                    logging.info("Secondary NVA is already ACTIVE")
                elif route.next_hop_ip_address == primary_ints[i]:
                    logging.info("Secondary NVA is NOT already ACTIVE")
                    # Update the route to use the secondary NVA
                    updated_route = Route(next_hop_type=RouteNextHopType.virtual_appliance, address_prefix=route.address_prefix, next_hop_ip_address=secondary_ints[i])

                    network_client.routes.begin_create_or_update(resource_group_name=resource_group_name,
                                                            route_table_name=route_table.name,
                                                            route_name=route.name,
                                                            route_parameters=updated_route).wait()

# Failback from secondary to primary
def start_failback():
    # Get the tag value from the environment variable
    tag_value = os.environ['FWUDRTAG']

    # List resources with the specified tag
    resources = resource_client.resources.list(filter=f"tagName eq 'nva_ha_udr' and tagValue eq '{tag_value}'")

    for resource in resources:
        logging.info("Contents of resource: %s", resource)

        resource_group_name = resource.id.split('/')[4]

        logging.info("Resource group for %s is %s", resource.name, resource_group_name)

        # Get the route table for the resource
        route_table = network_client.route_tables.get(resource_group_name=resource_group_name, route_table_name=resource.name)

        for route in route_table.routes:
            logging.info("Updating %s route %s", route_table.name, route)

            for i in range(len(primary_ints)):
                if route.next_hop_ip_address == primary_ints[i]:
                    logging.info("Primary NVA is already ACTIVE")
                elif route.next_hop_ip_address == secondary_ints[i]:
                    # Update the route to use the primary NVA
                    logging.info("Primary NVA is NOT already ACTIVE")
                    updated_route = Route(next_hop_type=RouteNextHopType.virtual_appliance, address_prefix=route.address_prefix, next_hop_ip_address=primary_ints[i])
                    network_client.routes.begin_create_or_update(resource_group_name=resource_group_name,
                                                            route_table_name=route_table.name,
                                                            route_name=route.name,
                                                            route_parameters=updated_route).wait()

# Get interfaces for NVAs
def get_fw_interfaces():
    # get the nics in FW1s resource group
    nics1 = list(network_client.network_interfaces.list(resource_group_name=os.environ['FW1RGNAME']))
    # get the nics in FW2s resource group
    nics2 = list(network_client.network_interfaces.list(resource_group_name=os.environ['FW2RGNAME']))
    nics = nics1 + nics2
    # get the FW1 vm
    vm1 = compute_client.virtual_machines.get(os.environ['FW1RGNAME'], os.environ['FW1NAME'], expand="instanceView")
    # get the FW2 vm
    vm2 = compute_client.virtual_machines.get(os.environ['FW2RGNAME'], os.environ['FW2NAME'], expand="instanceView")

    logging.info("vm1: %s", vm1)
    logging.info("vm2: %s", vm2)

    # get the primary and secondary private ip interfaces
    for nic in nics:
        logging.info("nic.virtual_machine.id: %s", nic.virtual_machine.id.lower())
        logging.info("vm1.id: %s", vm1.id.lower())
        logging.info("vm2.id: %s", vm2.id.lower())
        prv = [ip_config.private_ip_address for ip_config in nic.ip_configurations]
        logging.info("prv: %s", prv)
        if nic.virtual_machine and (nic.virtual_machine.id.lower() == vm1.id.lower()):
            primary_ints.extend(prv)
        if nic.virtual_machine and (nic.virtual_machine.id.lower() == vm2.id.lower()):
            secondary_ints.extend(prv)

# Entry point
def main(mytimer: TimerRequest) -> None:
    utc_timestamp = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')
    
    logging.info('Python timer trigger function ran at %s', utc_timestamp)

    logging.info("SUBSCRIPTIONID: %s", os.environ['SUBSCRIPTIONID'])
    logging.info("FW1RGNAME: %s", os.environ['FW1RGNAME'])
    logging.info("FW1NAME: %s", os.environ['FW1NAME'])
    logging.info("FW2RGNAME: %s", os.environ['FW2RGNAME'])
    logging.info("FW2NAME: %s", os.environ['FW2NAME'])
    logging.info("FWTRIES: %s", os.environ['FWTRIES'])
    logging.info("FWDELAY: %s", os.environ['FWDELAY'])
    logging.info("FWUDRTAG: %s", os.environ['FWUDRTAG'])
    logging.info("FWMONITOR: %s", os.environ['FWUDRTAG'])

    global credentials
    credentials = DefaultAzureCredential()

    global compute_client
    compute_client = ComputeManagementClient(credentials, os.environ['SUBSCRIPTIONID'])

    global network_client
    network_client = NetworkManagementClient(credentials, os.environ['SUBSCRIPTIONID'])

    global resource_client
    resource_client = ResourceManagementClient(credentials, os.environ['SUBSCRIPTIONID'])

    global primary_ints
    primary_ints = []
    global secondary_ints
    secondary_ints = []

    ctr_fw1 = 0
    ctr_fw2 = 0
    fw1_down = True
    fw2_down = True

    get_fw_interfaces()

    logging.info("primary_ints: %s", primary_ints)
    logging.info("secondary_ints: %s", secondary_ints)

    for ctr in range(int(os.environ['FWTRIES'])):
        if os.environ['FWMONITOR'] == 'VMStatus':
            fw1_down = test_vm_status(os.environ['FW1NAME'], os.environ['FW1RGNAME'])
            fw2_down = test_vm_status(os.environ['FW2NAME'], os.environ['FW2RGNAME'])

        if os.environ['FWMONITOR'] == 'TCPPort':
            fw1_down = not test_tcp_port(os.environ['FW1FQDN'], int(os.environ['FW1PORT']))
            fw2_down = not test_tcp_port(os.environ['FW2FQDN'], int(os.environ['FW2PORT']))

        logging.info(f"Pass {ctr + 1} of {int(os.environ['FWTRIES'])} - FW1Down is {fw1_down}, FW2Down is {fw2_down}")

        if fw1_down:
            ctr_fw1 += 1

        if fw2_down:
            ctr_fw2 += 1

        logging.info(f"Sleeping {os.environ['FWDELAY']} seconds")
        time.sleep(int(os.environ['FWDELAY']))

    fw1_down = False
    fw2_down = False

    if ctr_fw1 == int(os.environ['FWTRIES']):
        fw1_down = True

    if ctr_fw2 == int(os.environ['FWTRIES']):
        fw2_down = True

    if fw1_down and not fw2_down:
        logging.info('FW1 Down - Failing over to FW2')
        start_failover()
    elif not fw1_down and fw2_down:
        logging.info('FW2 Down - Failing back to FW1')
        start_failback()
    elif fw1_down and fw2_down:
        logging.info('Both FW1 and FW2 Down - Manual recovery action required')
    else:
        logging.info('Both FW1 and FW2 Up - No action is required')

if __name__ == "__main__":
    main()