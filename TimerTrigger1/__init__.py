# Python Azure Function to support HA for NVAs - Meraki VMx
# https://learn.microsoft.com/en-us/python/api/
#
import logging
import os
import time
import meraki
from datetime import datetime, timezone
from azure.functions import TimerRequest
from azure.identity import DefaultAzureCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network.models import Route, RouteNextHopType

# Check the Meraki network ID device status
def is_vpn_down(network_id):
    dashboard = meraki.DashboardAPI(suppress_logging=True)
    organization_id = os.environ['MERAKIORGANIZATIONID']
    response = dashboard.appliance.getOrganizationApplianceVpnStatuses(
        organization_id, networkIds=[network_id]
    )
    logging.info("Device status %s for network %s", response[0]['deviceStatus'], network_id)
    if len(response) != 1:
        raise Exception("getOrganizationApplianceVpnStatuses: Didn't get exactly 1 response")

    if response[0]['deviceStatus'] != 'online':
        logging.info("Device status %s for network %s", response[0]['deviceStatus'], network_id)
        return True
    
    return False

# Is the specified interface (ip) already set on the route tables?
def is_interface_active(interface):
    tag_value = os.environ['FWUDRTAG']
    tagged_resources = resource_client.resources.list(filter=f"tagName eq 'nva_ha_udr' and tagValue eq '{tag_value}'")
    logging.info("is_interface_active for: %s", interface)
    for resource in tagged_resources:
        resource_group_name = resource.id.split('/')[4]
        # Get the route table for the resource
        route_table = network_client.route_tables.get(resource_group_name=resource_group_name, route_table_name=resource.name)
        for route in route_table.routes:
            logging.info("Checking %s route %s", route_table.name, route)
            logging.info("Next hop: [%s] Interface: [%s]", route.next_hop_ip_address, interface)
            if route.next_hop_ip_address != interface:
                return False
    return True

# Switch to specific interface (ip)
def switch(interface):
    tag_value = os.environ['FWUDRTAG']
    tagged_resources = resource_client.resources.list(filter=f"tagName eq 'nva_ha_udr' and tagValue eq '{tag_value}'")
    logging.info("switch to: %s", interface)
    for resource in tagged_resources:
        logging.info("Contents of resource: %s", resource)

        resource_group_name = resource.id.split('/')[4]

        logging.info("Resource group for %s is %s", resource.name, resource_group_name)

        # Get the route table for the resource
        route_table = network_client.route_tables.get(resource_group_name=resource_group_name, route_table_name=resource.name)

        for route in route_table.routes:
            logging.info("Updating %s route %s", route_table.name, route)

            if route.next_hop_ip_address != interface:
                logging.info("Switching interfaces to %s", interface)
                # Update the route to use the new interface
                updated_route = Route(next_hop_type=RouteNextHopType.virtual_appliance, address_prefix=route.address_prefix, next_hop_ip_address=interface)

                network_client.routes.begin_create_or_update(resource_group_name=resource_group_name,
                                                        route_table_name=route_table.name,
                                                        route_name=route.name,
                                                        route_parameters=updated_route).wait()

# Entry point
def main(mytimer: TimerRequest) -> None:
    utc_timestamp = datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()

    if mytimer.past_due:
        logging.info('The timer is past due!')
    
    logging.info('Python timer trigger function ran at %s', utc_timestamp)

    logging.info("SUBSCRIPTIONID: %s", os.environ['SUBSCRIPTIONID'])
    logging.info("FWIP1: %s", os.environ['FWIP1'])
    logging.info("FWIP2: %s", os.environ['FWIP2'])
    logging.info("FWTRIES: %s", os.environ['FWTRIES'])
    logging.info("FWDELAY: %s", os.environ['FWDELAY'])
    logging.info("FWUDRTAG: %s", os.environ['FWUDRTAG'])
    logging.info("MERAKIORGANIZATIONID: %s", os.environ['MERAKIORGANIZATIONID'])
    logging.info("MERAKINETWORKID1: %s", os.environ['MERAKINETWORKID1'])
    logging.info("MERAKINETWORKID2: %s", os.environ['MERAKINETWORKID2'])

    global credentials
    credentials = DefaultAzureCredential()

    global network_client
    network_client = NetworkManagementClient(credentials, os.environ['SUBSCRIPTIONID'])

    global resource_client
    resource_client = ResourceManagementClient(credentials, os.environ['SUBSCRIPTIONID'])

    primary_interface = os.environ['FWIP1']
    secondary_interface = os.environ['FWIP2']

    ctr_fw1 = 0
    ctr_fw2 = 0
    fw1_down = True
    fw2_down = True
    fw1_active = False
    fw2_active = False

    logging.info("primary_interface: %s", primary_interface)
    logging.info("secondary_interface: %s", secondary_interface)

    fw1_active = is_interface_active(primary_interface)
    if (not fw1_active):
        fw2_active = is_interface_active(secondary_interface)

    logging.info("is FW1 already active: %s", fw1_active)
    logging.info("is FW2 already active: %s", fw2_active)

    for ctr in range(int(os.environ['FWTRIES'])):
        fw1_down = is_vpn_down(os.environ['MERAKINETWORKID1'])
        fw2_down = is_vpn_down(os.environ['MERAKINETWORKID2'])

        logging.info(f"Pass {ctr + 1} of {int(os.environ['FWTRIES'])} - FW1 is down? {fw1_down}, FW2 is down? {fw2_down}")

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

    if fw1_down and not fw2_down and not fw2_active:
        logging.warning('FW1 down and FW2 not active, switching to FW2')
        switch(secondary_interface)
    elif not fw1_down and not fw1_active:
        logging.warning('FW1 available but not active, switching to FW1')
        switch(primary_interface)
    elif fw2_down and not fw1_down and fw1_active:
        logging.warning('FW2 down but FW1 available and is active')
    elif fw1_down and fw2_down:
        logging.error('Both FW1 and FW2 down - manual recovery action required')
    else:
        logging.info('Both FW1 and FW2 up and FW1 primary, nothing to do')

if __name__ == "__main__":
    main()