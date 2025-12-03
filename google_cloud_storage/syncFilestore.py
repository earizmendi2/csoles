import os
from google.cloud import storage
db_name = "current_DB_name"
path = "/home/users/example_user/.local/share/Odoo/filestore/" + db_name
bucket_name = "google_bucket_name"
json_file_path = "/home/users/example_user/example.json"
client = storage.Client.from_service_account_json(json_file_path)
bucket = client.get_bucket(bucket_name)
for r, d, f in os.walk(path):
    for file in f:
        path = os.path.join(r, file)
        fname = path.split("filestore/")[1]
        blob = bucket.blob(fname)
        blob.upload_from_filename(path)
        print (fname)
print ("---upload finish-----")
