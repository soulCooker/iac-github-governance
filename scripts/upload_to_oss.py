import os
import argparse
import alibabacloud_oss_v2 as oss

parser = argparse.ArgumentParser(
    description="Create an OSS bucket for code storage")
parser.add_argument('--region', help='The region in which the bucket is located.',
                    default=os.environ.get('OSS_REGION'))
parser.add_argument('--bucket', help='The name of the bucket.',
                    default=os.environ.get('OSS_BUCKET'))
parser.add_argument('--key', help='The name of the object.', required=True)
parser.add_argument(
    '--file_path', help='The path of Upload file.', required=True)
parser.add_argument(
    '--unique_key', help='The commit id of the code package.')


def main():

    args = parser.parse_args()

    errors = []
    if not args.region:
        errors.append(
            "Region must be provided either as argument or via OSS_REGION environment variable")
    if not args.bucket:
        errors.append(
            "Bucket name must be provided either as argument or via OSS_BUCKET environment variable")

    if errors:
        for error in errors:
            print(f"Error: {error}")
        return 1

    credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()

    cfg = oss.config.load_default()
    cfg.credentials_provider = credentials_provider
    cfg.region = args.region

    client = oss.Client(cfg)

    # check if the same commit has been uploaded
    exist = client.is_object_exist(
        bucket=args.bucket,
        key=args.key,
    )
    if exist and args.unique_key:
        result = client.head_object(oss.HeadObjectRequest(
                                    bucket=args.bucket,
                                    key=args.key)
                                    )
        if result.metadata and result.metadata.get('unique-key') == args.unique_key:
            print(f'object {args.key} is exist\n'
                  f'version_id: {result.version_id},'
                  )
            return

    # upload file to oss
    meta_data = {}
    if args.unique_key:
        meta_data = {
            "unique-key": str(args.unique_key)
        }
    result = client.put_object_from_file(oss.PutObjectRequest(
        bucket=args.bucket,
        key=args.key,
        metadata=meta_data,
    ), args.file_path)
    print(f'upload file to oss successfully\n'
          f'status_code: {result.status_code},'
          f'request_id: {result.request_id},'
          f'version_id: {result.version_id},'
          )


if __name__ == "__main__":
    main()
