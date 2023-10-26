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

To check the availability of the NVA firewall, the function app code probes it in one of two ways:

-   By monitoring the state of the Azure virtual machines hosting the NVA firewall.

-   By testing whether there is an open port through the firewall to any server. For this option, the NVA must expose a socket via PIP for the function app code to test.

You choose the type of probe you want to use when you configure the function app.

## Prerequisites

This solution assumes that:

-   You have a subscription on Azure

-   Your subscription has an existing deployment of two NVA firewalls (probably Meraki)

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

The next step is to create and configure the function app using Azure Functions, and then deploy the code. You create the function app in the same Azure subscription that contains the NVA firewall virtual machine. You have the choice to configure the function app to monitor either the status of the virtual machines or the TCP port.

Before continuing, make sure to have the following values specific to this deployment:

-   Subscription ID for the Azure subscription in which the NVA firewall virtual
    machines are deployed.

-   Name of the virtual machine hosting the first NVA firewall instance.

-   Name of the virtual machine hosting the second NVA firewall instance.

-   Name of the resource group(s) containing the NVA firewall virtual machines.

-   Value you assigned earlier to the **nva\_ha\_udr** resource tag for each resource group containing route table resources.

The function app is deployed with a timer trigger defined in the function.json file. The default value for this timer trigger causes the function app to run every 30-seconds. It is not recommended to shorten this interval. You can lengthen it, but if you do, test the function app to validate that the function code executes frequently enough to respond to NVA firewall failover needs within an acceptable time period.

To create, configure, and deploy the function app:

1.  In Azure portal, log on to the same Azure subscription where the NVA firewall virtual machines are deployed.

2.  [Create a new function app](https://docs.microsoft.com/azure/azure-functions/functions-create-first-azure-function#create-a-function-app). Do not attempt to create or test the function code at this point—just create the function app.

3.  Navigate to the newly created function app and click the [Platform features](https://docs.microsoft.com/azure/azure-functions/functions-how-to-use-azure-function-app-settings#platform-features-tab) tab.

4.  Click [Application settings](https://docs.microsoft.com/azure/azure-functions/functions-how-to-use-azure-function-app-settings#settings) and add the following environment variables and values:

| Variable       | Value                                                                                   |
|----------------|-----------------------------------------------------------------------------------------|
| SUBSCRIPTIONID | Azure subscription ID                                                                   |
| FW1NAME        | Name of the virtual machine hosting the first NVA firewall instance                     |
| FW2NAME        | Name of the virtual machine hosting the second NVA firewall instance                    |
| FW1RGNAME      | Name of the resource group containing the NVA firewall virtual machine 1                |
| FW2RGNAME      | Name of the resource group containing the NVA firewall virtual machine 2                |
| FWUDRTAG       | Resource tag value                                                                      |
| FWTRIES        | *3* (enables three retries for checking firewall health before returning “Down” status) |
| FWDELAY        | *2* (enables two seconds between retries)                                               |
| FWMONITOR      | Either *VMStatus* or *TCPPort*                                                          |

5.  If you set FWMONITOR to *TCPPort*, add the following application setting variables and values:

| Variable | Value                                                                                      |
|----------|--------------------------------------------------------------------------------------------|
| FW1FQDN  | Publicly accessible FQDN or IP address for the first NVA firewall virtual machine instance |
| FW1PORT  | TCP port on which the first NVA firewall virtual machine instance is listening             |
| FW2FQDN  | Publicly accessible FQDN or IP address for second NVA firewall virtual machine instance    |
| FW2PORT  | TCP port on which the second NVA firewall virtual machine instance is listening            |

6.  It's easiest to deploy the code from inside Visual Studio Code, you need the Azure and Python plugins loaded [Instruction on how to use VSC with Python Azure Functions](https://learn.microsoft.com/en-us/azure/azure-functions/create-first-function-vs-code-python)

### Test the function app

After the Azure function app has been configured and deployed, use these steps to test automated failover between NVAs:

1.  If the Azure function app is configured such that FWMONITOR = "VMStatus", do the following:

    1.  Confirm that requests are flowing through the primary NVA (FW1) to internal applications.

    2.  Stop the virtual machine on the primary NVA (FW1).

    3.  Monitor the Azure function app logs to ensure that a failover is performed.

    4.  Confirm that you received an email alert about the failover process.

    5.  Confirm that traffic is now flowing through the secondary NVA (FW2) to internal applications.

2.  If the Azure function app is configured such that FWMONITOR = "TCPPort", do the following:

    1.  Confirm that requests are flowing through the primary NVA (FW1) to internal applications.

    2.  Apply a network security group (NSG) to the external NIC of the primary NVA (FW1) that blocks inbound network traffic on the TCP port being monitored.

    3.  Monitor the Azure function app Logs to ensure that a failover is performed.

    4.  Confirm that you received an email alert about the failover process.

    5.  Confirm that traffic is now flowing through the secondary NVA (FW2) to internal applications.

## Next steps

This solution is basic by design so you can tailor it to your environment. How you integrate this approach into your end-to-end environment can vary considerably depending on the security components or other controls you have deployed. For example, a common next step is to add more alerts and notifications. Another option is to integrate the logs from the function app with the tools you use for security and network monitoring. If your environment includes a layer of additional security controls around the NVAs, you might need to add more routes to the route tables.

## Learn more

* [Virtual network traffic routing: Custom routes](https://docs.microsoft.com/azure/virtual-network/virtual-networks-udr-overview#custom-routes)

* [Tutorial: Route network traffic with a route table using the Azure portal](https://docs.microsoft.com/azure/virtual-network/tutorial-create-route-table-portal)

* [Azure Functions documentation](https://docs.microsoft.com/azure/azure-functions/)

* [Azure Virtual Network Appliances](https://azure.microsoft.com/solutions/network-appliances/)

* [vMX_Setup_Guide_for_Microsoft_Azure](https://documentation.meraki.com/MX/MX_Installation_Guides/vMX_Setup_Guide_for_Microsoft_Azure)
