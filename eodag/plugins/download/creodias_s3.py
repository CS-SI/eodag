import os

import boto3
from botocore.exceptions import ClientError

from eodag.plugins.download.aws import AwsDownload

AWS_ACCESS_KEY_ID = os.environ.get(
    "EODAG__CREODIAS_S3__AUTH__CREDENTIALS__AWS_ACCESS_KEY_ID", "foo"
)
AWS_SECRET_ACCESS_KEY = os.environ.get(
    "EODAG__CREODIAS_S3__AUTH__CREDENTIALS__AWS_SECRET_ACCESS_KEY", "bar"
)


class CreodiasS3Download(AwsDownload):
    """
    Download on creodias s3 from their VMs
    """

    def _get_authenticated_objects_unsigned(self, bucket_name, prefix, auth_dict):
        """Auth strategy using no-sign-request"""

        raise ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "skip unsigned"}},
            "_get_authenticated_objects_unsigned",
        )

    def _get_authenticated_objects_from_auth_keys(self, bucket_name, prefix, auth_dict):
        """Auth strategy using RequestPayer=requester and ``aws_access_key_id``/``aws_secret_access_key``
        from provided credentials"""

        s3_session = boto3.session.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        )
        s3_resource = s3_session.resource(
            "s3", endpoint_url=getattr(self.config, "base_uri", None)
        )
        objects = s3_resource.Bucket(bucket_name).objects.filter()
        list(objects.filter(Prefix=prefix).limit(1))
        self.s3_session = s3_session
        return objects
