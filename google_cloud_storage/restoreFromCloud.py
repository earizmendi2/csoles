from google.cloud import storage
import os
previous_db_name = "previous_DB_name"
db_name = "current_db_name"
local_path = "/home/users/example_user/.local/share/Odoo/filestore/" + db_name
bucket_name = "webkul-odoo-filestore"
json_file_path = "/home/users/example_user/example.json"
client = storage.Client.from_service_account_json(json_file_path)
bucket = client.get_bucket(bucket_name)


def get_location(path):

    dir = (path[::-1])[(path[::-1].find("/")):][::-1]
    file_name = (path[::-1])[:(path[::-1].find("/"))][::-1]
    return (dir, file_name)


def download_dir(prefix, local_path, bucket):

    """
    params:
    - prefix: dbname to match in google cloud storage
    - local: local path to folder in which to place files
    - bucket: Google Cloud Storage bucket with target contents
    """
    blobs = bucket.list_blobs(prefix= prefix)
    for blob in blobs:
        dir, file_name = get_location(blob.name)
        dest_pathname = os.path.join(local_path, dir)
        if not os.path.exists(os.path.dirname(dest_pathname)):
            os.makedirs(os.path.dirname(dest_pathname))
        destination_uri = dest_pathname + file_name
        blob.download_to_filename(destination_uri)

    print ("=======Finish Download========")


download_dir(previous_db_name, local_path, bucket)
