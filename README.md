# azure-python-ha-nva-fo
Azure Python Function to manage NVA failover (designed for Meraki VMx)

This is based on:

https://github.com/ScottMonolith/ha-nva-fo

https://github.com/Azure/ha-nva-fo

It uses the Azure Functions Python v1 "programming model" 

https://learn.microsoft.com/en-us/azure/azure-functions/functions-reference-python

This solution uses two Azure virtual machines to host the NVA firewall in an active-passive configuration.

The failover of UDR table entries is automated by a next-hop address set to the IP address of an interface on the active NVA firewall virtual machine. The automated failover logic is hosted in a function app that you create using [Azure Functions](https://docs.microsoft.com/azure/azure-functions/).  Function apps offer several advantages. The failover code runs as a serverless function inside Azure Functions—deployment is convenient, cost-effective, and easy to maintain and customize. In addition, the function app is hosted within Azure Functions, so it has no dependencies on the virtual network. If changes to the virtual network impact the NVA firewalls, the function app continues to run
independently. Testing is more accurate as well, because it takes place outside the virtual network using the same route as the inbound client requests.

To check the availability of the NVA firewall, the function app code probes it by monitoring the device status of the Meraki networks/appliance using the Meraki API.


## Prerequisites

This solution assumes that:

-   You have a subscription on Azure

-   Your subscription has an existing deployment of two Meraki VMx firewalls 

-   You know how to route network traffic with a [route table](https://docs.microsoft.com/azure/virtual-network/tutorial-create-route-table-portal).

-   Visual Studio Code installed to deploy the solution [Download Visual Studio Code](https://code.visualstudio.com/download)

### Set up Azure resources

To get started, you need to assign permissions to your function app.

After you assign the permissions, you apply resource tags to the route table resources. By applying tags, you can easily retrieve all the route table resources in your subscription by name. The function app deployed in this solution automates the failover of user-defined route table entries with a next hop address set to the IP address of an interface on the first NVA firewall virtual machine. You assign a resource tag name and value to each route table resource for which the function app will manage automated failover.

To set up the Azure resources:

1.  Setup permissions for your function app under the function apps "Identity" option you can create a "Sytem assigned" service principal.  For the resource group containing the NVA firewall virtual machines, assign the **Reader** role. For the resource group(s) containing route table resources, assign the **Contributor** role to the new principal.

2.  [Configure the resource tag name and value](https://docs.microsoft.com/azure/azure-resource-manager/resource-group-using-tags#portal) for each route table resource managed by the function app using the following:

    1.  For the name, use **nva\_ha\_udr**.

    2.  For the value, enter text that describes this deployment. You will need this value for the next set of steps (note that the value is the case-sensitive).

### Set up Azure Functions

The next step is to create and configure the function app using Azure Functions, and then deploy the code. You create the function app in the same Azure subscription that contains the NVA firewall virtual machine. 

Before continuing, make sure to have the following values specific to this deployment:

-   Subscription ID for the Azure subscription in which the NVA firewall virtual
    machines are deployed.

-   Private IPs of the virtual machine hosting the first & second NVA firewall instance.

-   Meraki Organisation ID, and the Network ID for both networks that the first & second NVA instances are in.
    https://dashboard.meraki.com/api/v0/organizations (id field)
    https://api.meraki.com/api/v0/organizations/{id}/networks  (id field prefixed with N_)

-   Meraki API key (created under Organization / API & Webhooks in Meraki dashboard)

-   Value you assigned earlier to the **nva\_ha\_udr** resource tag for each resource group containing route table resources.

The function app is deployed with a timer trigger defined in the function.json file. The default value for this timer trigger causes the function app to run every 30-seconds. It is not recommended to shorten this interval. You can lengthen it, but if you do, test the function app to validate that the function code executes frequently enough to respond to NVA firewall failover needs within an acceptable time period.

To create, configure, and deploy the function app:

1.  In Azure portal, log on to the same Azure subscription where the NVA firewall virtual machines are deployed.

2.  [Create a new function app](https://docs.microsoft.com/azure/azure-functions/functions-create-first-azure-function#create-a-function-app). Do not attempt to create or test the function code at this point—just create the function app.

3.  Navigate to the newly created function app and click the [Platform features](https://docs.microsoft.com/azure/azure-functions/functions-how-to-use-azure-function-app-settings#platform-features-tab) tab.

4.  Click [Application settings](https://docs.microsoft.com/azure/azure-functions/functions-how-to-use-azure-function-app-settings#settings) and add the following environment variables and values:

| Variable                 | Value                                                                                   |
|--------------------------|-----------------------------------------------------------------------------------------|
| SUBSCRIPTIONID           | Azure subscription ID                                                                   |
| FWIP1                    | Private IP of the virtual machine hosting the first NVA firewall instance               |
| FWIP2                    | Private IP of the virtual machine hosting the second NVA firewall instance              |
| FWUDRTAG                 | Resource tag value                                                                      |
| FWTRIES                  | *3* (enables three retries for checking firewall health before returning “Down” status) |
| FWDELAY                  | *2* (enables two seconds between retries)                                               |
| MERAKIORGANIZATIONID     | Meraki Organisation ID for API call                                                     |
| MERAKINETWORKID1         | Meraki Network ID (N_xxxxxxx) for the first NVA firewall instance                       |
| MERAKINETWORKID2         | Meraki Network ID (N_xxxxxxx) for the second NVA firewall instance                      |
| MERAKI_DASHBOARD_API_KEY | Meraki API key for the Organisation                                                     |

5.  It's easiest to deploy the code from inside Visual Studio Code, you need the Azure and Python plugins loaded [Instruction on how to use VSC with Python Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/create-first-function-vs-code-python)

### Test the function app

After the Azure function app has been configured and deployed, use these steps to test automated failover between NVAs:

    1.  Confirm that requests are flowing through the primary NVA (FW1) to internal applications.

    2.  Stop the virtual machine on the primary NVA (FW1).

    3.  Monitor the Azure function app logs to ensure that a failover is performed.

    4.  Confirm that traffic is now flowing through the secondary NVA (FW2) to internal applications.


## Next steps

This solution is basic by design so you can tailor it to your environment. How you integrate this approach into your end-to-end environment can vary considerably depending on the security components or other controls you have deployed. For example, a common next step is to add more alerts and notifications. Another option is to integrate the logs from the function app with the tools you use for security and network monitoring. If your environment includes a layer of additional security controls around the NVAs, you might need to add more routes to the route tables.

## Learn more

* [Virtual network traffic routing: Custom routes](https://docs.microsoft.com/azure/virtual-network/virtual-networks-udr-overview#custom-routes)

* [Tutorial: Route network traffic with a route table using the Azure portal](https://docs.microsoft.com/azure/virtual-network/tutorial-create-route-table-portal)

* [Azure Functions documentation](https://docs.microsoft.com/azure/azure-functions/)

* [Azure Virtual Network Appliances](https://azure.microsoft.com/solutions/network-appliances/)

* [vMX_Setup_Guide_for_Microsoft_Azure](https://documentation.meraki.com/MX/MX_Installation_Guides/vMX_Setup_Guide_for_Microsoft_Azure)
