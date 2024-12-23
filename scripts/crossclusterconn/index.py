import time
import json
import boto3
import os
from crhelper import CfnResource
import logging

logger = logging.getLogger()
logger.setLevel('INFO')

nat_instance = os.environ["NATId"]

helper = CfnResource(log_level='INFO')

@helper.create
def create(event, context):
	connection_alias = event['ResourceProperties']['ConnectionAlias']
	local_account = event['ResourceProperties']['LocalAccount']
	local_domain = event['ResourceProperties']['LocalDomain']
	local_region = event['ResourceProperties']['LocalRegion']
	remote_account = event['ResourceProperties']['RemoteAccount']
	remote_domain = event['ResourceProperties']['RemoteDomain']
	remote_region = event['ResourceProperties']['RemoteRegion']	

# Start up the NAT instance needed to get to the Internet for the following calls
	start_instance("Create", local_region, nat_instance)

	localclient = boto3.client('opensearch', region_name=local_region)
	outresponse = localclient.create_outbound_connection(
		LocalDomainInfo={
			'AWSDomainInformation': {
				'OwnerId': local_account,
				'DomainName': local_domain,
				'Region': local_region
				}
		},
		RemoteDomainInfo={
			'AWSDomainInformation': {
				'OwnerId': remote_account,
				'DomainName': remote_domain,
				'Region': remote_region
				}	
		},
		ConnectionAlias=connection_alias,
		ConnectionMode='DIRECT',
		ConnectionProperties={
			'CrossClusterSearch': {
				'SkipUnavailable': 'ENABLED'
			 	}
			}
		)

	connectionId = outresponse['ConnectionId']
	#Allow for PENDING_ACCEPTANCE stage to be reached - polling could improve on this
	time.sleep(60)

	do_inbound = False
	outresponse = localclient.describe_outbound_connections()
	connections = outresponse['Connections']
	for thing in connections:
		logger.info(f"Looking at connection: {thing}")
		if thing['ConnectionId'] == connectionId and thing['ConnectionStatus']['StatusCode'] == 'PENDING_ACCEPTANCE':
			do_inbound = True
			break

	if not do_inbound:
			return_msg = "Outbound connection creation error - either the connectionId not available or outbound connection is not in PENDING_ACCEPTANCE state."
			logger.info(return_msg)
			helper.Data['ReturnMsg'] = return_msg
			stop_instance("Create", local_region, nat_instance)
			return

# See if this is a cross account replication setup
	if remote_account == local_account:
		remoteclient = boto3.client('opensearch', region_name=remote_region)
	else:
		logger.info(f"Assuming role in remote_account {remote_account} to accept inbound request.")
		boto_sts=boto3.client('sts', region_name=local_region)
		remote_role = os.environ["CrossAccountIamRoleArn"]
		stsresponse = boto_sts.assume_role(RoleArn=remote_role, RoleSessionName='opensearchrepl')
		session_id = stsresponse["Credentials"]["AccessKeyId"]
		session_key = stsresponse["Credentials"]["SecretAccessKey"]
		session_token = stsresponse["Credentials"]["SessionToken"]
		remoteclient = boto3.client('opensearch', region_name=remote_region, aws_access_key_id=session_id, aws_secret_access_key=session_key, aws_session_token=session_token)

	inresponse = remoteclient.accept_inbound_connection(
	    ConnectionId=connectionId
	)

	status_code = inresponse['Connection']['ConnectionStatus']['StatusCode']
	return_msg = f"The status_code for inbound acceptance is {status_code}."
	logger.info(return_msg)
	helper.Data['ReturnMsg'] = return_msg
	stop_instance("Create", local_region, nat_instance)


@helper.update
def no_op(_, __):
    pass

@helper.delete
def delete(event, context):
	connection_alias = event['ResourceProperties']['ConnectionAlias']
	local_region = event['ResourceProperties']['LocalRegion']
	
	start_instance("Delete", local_region, nat_instance)

	localclient = boto3.client('opensearch', region_name=local_region)
	connection_deleted = False

	outresponse = localclient.describe_outbound_connections()
	connections = outresponse['Connections']
	for thing in connections:
		if thing['ConnectionAlias'] == connection_alias and thing['ConnectionStatus']['StatusCode'] == 'ACTIVE':
			outresponse = localclient.delete_outbound_connection(ConnectionId=thing['ConnectionId'])
			status_code = outresponse['Connection']['ConnectionStatus']['StatusCode']
			return_msg = f"The status_code for outbound deletion is {status_code}."
			connection_deleted = True
			break
		
	if not connection_deleted:
			return_msg = "Error - either the connection alias was not found or deletion failed."

	logger.info(return_msg)
	helper.Data['ReturnMsg'] = return_msg
	stop_instance("Delete", local_region, nat_instance)


def start_instance(action, region, instance):
	ec2client = boto3.client('ec2', region_name=region)
	ec2response = ec2client.start_instances(InstanceIds=[ instance ])
	logger.info(f"{action}: Response to starting the NAT instance: {ec2response}")
	time.sleep(120)
	logger.info(f"{action}: Internet now should be reachable via NAT instance. Proceeding with opensearch API calls.")

def stop_instance(action, region, instance):
	ec2client = boto3.client('ec2', region_name=region)
	ec2response = ec2client.stop_instances(InstanceIds=[ instance ])
	logger.info(f"{action}: Response to stopping the NAT instance: {ec2response}")

def handler(event, context):
	logger.info("EVENT")
	logger.info(event)
	helper(event, context)