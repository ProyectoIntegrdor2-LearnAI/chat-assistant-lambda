# IAM Role Permissions Required for Chat Assistant Lambda Deployment

## Issue
The GitHub Actions workflow is failing because the `gh-actions-deploy-role` IAM role doesn't have permissions to create DynamoDB tables and Lambda layers.

## Required IAM Permissions

The role needs the following permissions added to its inline policy or a new policy attachment:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:CreateTable",
        "dynamodb:DeleteTable",
        "dynamodb:DescribeTable",
        "dynamodb:ListTagsOfResource",
        "dynamodb:TagResource",
        "dynamodb:UntagResource"
      ],
      "Resource": "arn:aws:dynamodb:us-east-2:974724840334:table/learnia-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "lambda:CreateFunction",
        "lambda:DeleteFunction",
        "lambda:GetFunction",
        "lambda:UpdateFunction",
        "lambda:PublishLayerVersion",
        "lambda:DeleteLayerVersion",
        "lambda:CreateEventSourceMapping",
        "lambda:DeleteEventSourceMapping",
        "lambda:AddPermission",
        "lambda:RemovePermission"
      ],
      "Resource": [
        "arn:aws:lambda:us-east-2:974724840334:function:learnia-*",
        "arn:aws:lambda:us-east-2:974724840334:layer:learnia-*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "apigateway:*"
      ],
      "Resource": "arn:aws:apigateway:us-east-2::/restapis/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "iam:PassRole",
        "iam:CreateRole",
        "iam:DeleteRole",
        "iam:GetRole",
        "iam:PutRolePolicy",
        "iam:DeleteRolePolicy",
        "iam:AttachRolePolicy",
        "iam:DetachRolePolicy"
      ],
      "Resource": "arn:aws:iam::974724840334:role/learnia-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::learnia-sam-artifacts-us-east-2/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:CreateStack",
        "cloudformation:DeleteStack",
        "cloudformation:DescribeStacks",
        "cloudformation:DescribeStackEvents",
        "cloudformation:GetTemplateSummary",
        "cloudformation:ListStackResources",
        "cloudformation:UpdateStack",
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet"
      ],
      "Resource": "arn:aws:cloudformation:us-east-2:974724840334:stack/learnia-*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/us.amazon.nova-pro-v1:0"
    },
    {
      "Effect": "Allow",
      "Action": [
        "cloudwatch:PutMetricData"
      ],
      "Resource": "*"
    }
  ]
}
```

## Steps to Update the IAM Role

1. Go to the AWS Console
2. Navigate to IAM > Roles
3. Find the `gh-actions-deploy-role` role
4. Add the permissions above by either:
   - Creating a new inline policy with the JSON above
   - Or attaching existing AWS managed policies if available

## Alternative: Use Simplified Deployment

If you want to simplify permissions, you can use AWS managed policies:
- `AWSCloudFormationFullAccess`
- `AWSLambda_FullAccess`
- `AmazonDynamoDBFullAccess`
- `IAMFullAccess`
- `AmazonS3FullAccess`

However, the inline policy with specific resource restrictions is more secure.
