# OpenSearch Cross-Cluster Replication for Disaster Recovery

This project implements a cross-cluster replication setup for OpenSearch domains to enable data replication for high availability and disaster recovery across AWS regions and/or AWS accounts.

For the purpose of demonstration only, this project creates all the infrastructure needed to support OpenSearch cross-cluster replication connectivity, including VPCs, Subnets, OpenSearch Clusters, NAT instance, Lambda function and Custom Resource invoking this function to create and destroy a Cross-Cluster Connection.

Note: the solution does not create the S3 bucket needed to host the zip file for the Lambda function. Please create one if needed.

## Repository Structure

```
.
├── config
│   ├── es-follower
│   │   ├── config.yaml
│   │   ├── crossaccountcr.yaml
│   │   ├── crossaccountlambda.yaml
│   │   ├── crossclustercr.yaml
│   │   ├── crossclusterlambda.yaml
│   │   ├── natinstance.yaml
│   │   ├── opensearch.yaml
│   │   ├── sg.yaml
│   │   ├── subnets.yaml
│   │   ├── tunnelinstance.yaml
│   │   └── vpc.yaml
│   ├── es-leader
│   │   ├── config.yaml
│   │   ├── opensearch.yaml
│   │   ├── subnets.yaml
│   │   └── vpc.yaml
│   └── es-leader-crossacount
│       ├── config.yaml
│       ├── crossaccountiamrole.yaml
│       ├── opensearch.yaml
│       ├── subnets.yaml
│       └── vpc.yaml
├── scripts
│   └── crossclusterconn
│       └── index.py
├── templates
│   ├── crossaccountiamrole.yaml
│   ├── crossaccountlambda.yaml
│   ├── crossclustercr.yaml
│   ├── crossclusterlambda.yaml
│   ├── natinstance.yaml
│   ├── opensearch.yaml
│   ├── sg.yaml
│   ├── tunnelinstance.yaml
│   ├── us-east-1
│   │   └── subnets.yaml
│   ├── us-west-2
│   │   └── subnets.yaml
│   ├── utilinstances.yaml
│   ├── vpc.yaml
│   └── vpcwithigw.yaml
└── vars.yaml
```

Key Files:
- `vars.yaml`: Contains global variables for the project.
- `config/es-follower/config.yaml`: Configuration for the follower OpenSearch domain.
- `config/es-leader/config.yaml`: Configuration for the leader OpenSearch domain (when using same AWS account as follower )
- `config/es-leader-crossacount/config.yaml`: Configuration for the leader OpenSearch domain (when using a different AWS account than the follower )
- `scripts/crossclusterconn/index.py`: Python script for managing cross-cluster connections.
- `templates/*.yaml`: CloudFormation templates for various resources.

## Usage Instructions

### Prerequisites

- AWS CLI installed and configured with appropriate permissions
- Python 3.7 or later
- boto3 library installed

### Installation

1. Clone the repository:
   ```
   git clone <repository_url>
   cd <repository_name>
   ```
2. Configure AWS CLI with the necessary profiles:
   ```
   aws configure --profile follower-account
   aws configure --profile leader-account
   ```

3. Install required Python packages (using a virtual environment is strongly recommended).
   ```
   python3 -m venv .
   source ./bin/activate
   pip install boto3
   pip install -r requirements.txt
   ```

### Configuration

1. Update the `vars.yaml` file with your specific values:
   ```yaml
   followerregion: <follower-region>
   followerprofile: <follower-account>
   leaderregion: <leader-region>>
   leaderprofile: <follower-account OR leader-account>
   opensearchuser: admin
   opensearchpw: <opensearch-admin-password>
   opensearchconnalias: <name-for-opensearch-connection>
   ```
Note that the using the same AWS profile for followerprofile and leaderprofile, as shown above, will result in a non cross-account implementation.

2. If desired, edit the IP addresses used in config/<*>/subnet.yaml,vpc.yaml.

2. Review the `template/opensearch.yaml` file and alter as desired for the cluster configuration.

3. Zip the Lambda function and packages needed (crhelper supports Custom Resource lifecycle management)
   ```
   cd scripts/crossclusterconn
   pip install -r requirements.txt
   zip crossclusterconn.zip index.py crhelper*
   ```

4. Edit the S3Bucket location you will use to host the code for this Lambda function in file `templates/crossclusterlambda.yaml`. Upload the code to this location. Note that this bucket needs to be in the same region as the follower region.

### Deployment

1. Deploy the leader OpenSearch environment:
   ```
   sceptre create es-leader/vpc.yaml
   sceptre create es-leader/subnet.yaml
   sceptre create es-leader/opensearch.yaml
   ```

(If you are deploying a crossaccount setup, substitute with "es-leader-crossacount/* for the above.)

2. Deploy the follower OpenSearch environment:
   ```
   sceptre create es-follower/vpc.yaml
   sceptre create es-follower/sg.yaml
   sceptre create es-follower/subnet.yaml
   sceptre create es-follower/opensearch.yaml
   sceptre create es-follower/natinstance.yaml
   ```

3. Set up cross-cluster replication:
   ```
   sceptre create es-follower/crossclusterlambda.yaml
   sceptre create es-follower/crossclustercr.yaml
   ```

### Validation

Inspect the OpenSearch Console to verify that the "Connection" name is displayed on either the Follower or the Leader OpenSearch cluster.

### Troubleshooting

- If the cross-cluster connection fails, check the CloudWatch logs for the Lambda function in the follower account.
- Ensure that the security groups and VPC settings allow communication between the leader and follower domains.
- Verify that the IAM roles have the necessary permissions for cross-account access.


## Infrastructure

The infrastructure for this project, as configured, is defined using AWS CloudFormation templates. Key resources include:

- OpenSearch Domains:
  - Leader domain in us-east-1
  - Follower domain in us-west-2
- VPCs and Subnets:
  - Separate VPCs for leader and follower domains
  - Private subnets for OpenSearch domains
  - A public subnet for a NAT instance in the follower environment
  - IGW for Public Access in follower environment
  - Private Endpoints for EC2, STS, SSM
- Security Groups:
  - For OpenSearch domains
  - For the Lambda function
  - For the NAT instance
  - For Private Endpoints
- EC2
  - NAT Instance in follower environment
- IAM Roles:
  - Cross-account role for replication
  - Lambda execution role
- Lambda Functions:
  - For managing cross-cluster connections
- Transit Gateway:
  - For inter-region connectivity

The infrastructure is designed to provide secure and efficient cross-region and cross-account replication for disaster recovery purposes.