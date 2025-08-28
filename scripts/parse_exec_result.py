#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OSS Result Parser and Formatter

This module provides functionality to poll, download, and format execution results from OSS.
"""

import os
import json
import time
import argparse
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlparse
import alibabacloud_oss_v2 as oss

def parse_oss_url(oss_url: str) -> Tuple[Optional[str], Optional[str], Optional[str], list[str]]:
    """Parse OSS URL to extract bucket, key, and region information.
    
    Supports format:
    - oss::https://bucket-name.oss-region.aliyuncs.com/path/to/object
    """
    errors = []

    if not oss_url:
        errors.append('OSS URL cannot be empty')
        return None, None, None, errors

    try:
        # Handle oss::https:// format
        if oss_url.startswith('oss::https://'):
            # Remove oss::https:// prefix
            url_without_prefix = oss_url[13:]
        else:
            errors.append('OSS URL must start with oss::https://')
            return None, None, None, errors

        # Parse the URL using urllib
        parsed_url = urlparse(f"https://{url_without_prefix}")

        if not parsed_url.hostname:
            errors.append('Invalid OSS URL format: missing hostname')
            return None, None, None, errors

        if not parsed_url.path or parsed_url.path == '/':
            errors.append('Invalid OSS URL format: missing object key')
            return None, None, None, errors

        # Extract object key (remove leading slash)
        object_key = parsed_url.path[1:] if parsed_url.path.startswith(
            '/') else parsed_url.path

        if not object_key:
            errors.append('Object key cannot be empty')
            return None, None, None, errors

        # Parse hostname: bucket-name.oss-region.aliyuncs.com
        hostname = parsed_url.hostname

        if not hostname.endswith('.aliyuncs.com'):
            errors.append('OSS URL must use aliyuncs.com domain')
            return None, None, None, errors

        # Remove .aliyuncs.com suffix and split by dots
        host_without_suffix = hostname[:-13]  # Remove '.aliyuncs.com'
        host_parts = host_without_suffix.split('.')

        if len(host_parts) < 2:
            errors.append(
                'Invalid OSS URL format: missing bucket or region information')
            return None, None, None, errors

        # First part is bucket name
        bucket_name = host_parts[0]

        if not bucket_name:
            errors.append('Bucket name cannot be empty')
            return None, None, None, errors

        # Find the oss-region part (should start with 'oss-')
        region = None
        for part in host_parts[1:]:
            if part.startswith('oss-'):
                region = part[4:]  # Remove 'oss-' prefix
                break

        if not region:
            errors.append('Region information not found in URL')
            return None, None, None, errors

        return bucket_name, object_key, region, errors

    except Exception as e:
        errors.append(f'Failed to parse OSS URL: {str(e)}')
        return None, None, None, errors


def create_oss_client(region: str) -> Optional[oss.Client]:
    """Create OSS client with proper credentials and configuration."""
    try:

        credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()

        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = region

        return oss.Client(cfg)

    except Exception as e:
        print(f"Failed to create OSS client: {str(e)}")
        return None


def get_oss_object_content(client: oss.Client, bucket: str, key: str) -> Optional[str]:
    """Get object content from OSS if it exists."""
    try:
        if not client.is_object_exist(bucket=bucket, key=key):
            return None

        result = client.get_object(
            oss.GetObjectRequest(bucket=bucket, key=key))

        if result and result.body:
            content = result.body.read()
            return content.decode('utf-8') if isinstance(content, bytes) else str(content)

        return None

    except Exception as e:
        print(f"Error getting object content: {str(e)}")
        return None


def format_execution_result(data: Dict[str, Any]) -> str:
    """Format execution result data for display in Markdown format."""
    try:
        output = []

        # Main execution info
        execution_id = data.get('id', 'Unknown')
        status = data.get('triggeredStatus', 'Unknown')
        message = data.get('message', '')

        # Status with emoji
        status_emoji = "✅" if status == "Success" else "❌" if status == "Errored" else "⚪"

        output.append("## 📋 Execution Information")
        output.append("")
        output.append(f"| Field | Value |")
        output.append(f"|-------|-------|")
        output.append(f"| **Execution ID** | `{execution_id}` |")
        output.append(f"| **TriggeredStatus** | {status_emoji} {status} |")

        if message:
            output.append(f"| **Message** | {message} |")

        output.append("")

        # Stack details
        stacks = data.get('stacks', [])
        if stacks:
            output.append(f"## 📦 Stacks ({len(stacks)} total)")
            output.append("")

            for i, stack in enumerate(stacks, 1):
                stack_name = stack.get('stackName', 'Unknown')
                stack_status = stack.get('stackStatus', 'Unknown')

                # Stack status with emoji
                stack_emoji = "✅" if stack_status == "Deployed" else "❌" if stack_status == "Errored" else "⚪"

                output.append(f"### {i}. Stack: {stack_name}")
                output.append("")
                output.append(f"**Status:** {stack_emoji} {stack_status}")
                output.append("")

                # Deployment details
                deployments = stack.get('deployments', [])
                if deployments:
                    output.append(
                        f"#### 🚀 Deployments ({len(deployments)} total)")
                    output.append("")

                    # Create deployment table
                    output.append(
                        "| Deployment | Status | Job Result | Details |")
                    output.append(
                        "|------------|--------|------------|---------|")

                    for deployment in deployments:
                        deploy_name = deployment.get('deploymentName') or deployment.get(
                            'deployment_name', 'Unknown')
                        deploy_status = deployment.get('status', 'Unknown')
                        job_result = deployment.get('jobResult', '')
                        deploy_url = deployment.get('url', '')

                        # Deployment status with emoji
                        deploy_emoji = {
                            "Applied": "✅",
                            "Planned": "✅",
                            "Errored": "❌"
                        }.get(deploy_status, "⚪")

                        # Format job result
                        job_result_display = f"`{job_result}`" if job_result else "-"

                        # Format details link
                        details_link = f"[View Details]({deploy_url})" if deploy_url else "-"

                        output.append(
                            f"| {deploy_name} | {deploy_emoji} {deploy_status} | {job_result_display} | {details_link} |")

                    output.append("")
                else:
                    output.append("#### 🚀 Deployments")
                    output.append("")
                    output.append("*No deployments found*")
                    output.append("")

                # Add separator between stacks
                if i < len(stacks):
                    output.append("---")
                    output.append("")
        else:
            output.append("## 📦 Stacks")
            output.append("")
            output.append("*No stacks found*")
            output.append("")

        return "\n".join(output)

    except Exception as e:
        return f"## ❌ Error\n\nError formatting result: `{str(e)}`"


def poll_and_process_oss_result(oss_url: str, max_wait_time: int = 3600, output_file: Optional[str] = None) -> Optional[str]:
    """Poll OSS URL for result file, download and format when available."""
    poll_interval = 10  # Fixed polling interval: 10 seconds

    print(f"\n🔍 Starting to poll OSS URL: {oss_url}")
    print(
        f"⏱️  Poll interval: {poll_interval}s, Max wait time: {max_wait_time}s")
    if output_file:
        print(f"📄 Output will be written to: {output_file}")
    print("")

    # Parse OSS URL
    bucket, key, region, parse_errors = parse_oss_url(oss_url)
    if parse_errors:
        print("❌ URL parsing errors:")
        for error in parse_errors:
            print(f"   - {error}")
        return None

    if not bucket or not key or not region:
        print("❌ Missing required URL components after parsing")
        return None

    print(f"📋 Parsed URL: Bucket={bucket}, Key={key}, Region={region}")
    print("")

    # Create OSS client
    client = create_oss_client(region)
    if not client:
        print("❌ Failed to create OSS client")
        return None

    print("✅ OSS client created successfully")
    print("")

    # Start polling
    start_time = time.time()
    attempt = 0

    while True:
        attempt += 1
        elapsed_time = time.time() - start_time

        print(f"🔄 Attempt #{attempt} (Elapsed: {elapsed_time:.1f}s)")

        # Check if max wait time exceeded
        if elapsed_time > max_wait_time:
            print(f"⏰ Maximum wait time ({max_wait_time}s) exceeded")
            return None

        # Check if object exists and get content
        content = get_oss_object_content(client, bucket, key)
        if content:
            print(f"✅ Object found! Downloaded {len(content)} characters")

            # Parse JSON
            try:
                data = json.loads(content)
                print("✅ JSON content validated successfully")
                print("")
                
                # Format the result
                formatted_result = format_execution_result(data)
                
                # Write to file if output_file is specified
                if output_file:
                    try:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(formatted_result)
                        print(f"📄 Result written to file: {output_file}")
                    except Exception as e:
                        print(f"⚠️  Warning: Failed to write to file {output_file}: {str(e)}")
                
                return formatted_result
            except json.JSONDecodeError as e:
                print(f"❌ Invalid JSON format: {str(e)}")
                return None
            except Exception as e:
                print(f"❌ Failed to parse content: {str(e)}")
                return None
        else:
            print(f"⏳ Object not found, waiting {poll_interval}s...")
            time.sleep(poll_interval)


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Poll, download and format execution results from OSS"
    )
    parser.add_argument(
        '--oss-url',
        help='OSS URL to poll in format: oss://bucket-name.oss-region.aliyuncs.com/path/to/file'
    )
    parser.add_argument(
        '--max-wait-time',
        type=int,
        default=3600,
        help='Maximum wait time in seconds (default: 3600)'
    )
    parser.add_argument(
        '--output-file',
        type=str,
        help='Output file path to write the formatted result (optional)'
    )

    args = parser.parse_args()

    try:
        result = poll_and_process_oss_result(
            oss_url=args.oss_url,
            max_wait_time=args.max_wait_time,
            output_file=args.output_file
        )

        if result:
            print(result)
        else:
            print("❌ Failed to process OSS result")
            exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user")
        exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        exit(1)


if __name__ == "__main__":
    main()
