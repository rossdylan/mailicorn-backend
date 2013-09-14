import boto
import json
import time
import memcache


memcache_host = 'mailicache.ucd9qd.cfg.use1.cache.amazonaws.com:11211'
client = memcache.Client([memcache_host], debug=0)


def get_msg_body(mid):
    return client.get(mid)

bucket = boto.connect_s3().get_bucket('archive.mailicorn.com')


def archive_mail(mid):
    body = get_msg_body(mid)
    key = bucket.new_key(mid)
    key.set_contents_from_string(body)
    return True


cs = boto.connect_cloudsearch()

mail_search = cs.lookup('mailicorn-1')
doc_service = mail_search.get_document_service()
search_service = mail_search.get_search_service()


def index_document(mid):
    doc_service.add(mid, mid, get_msg_body(mid))


sqs = boto.connect_sqs()


def apply_rule(mid, queue_name=None):
    if queue_name is None:
        queue_name = 'matched-action'
    q = sqs.get_queue(queue_name)
    if search_service.search(bq="(field mid '%s')" % mid):
        sqs.send_message(q, json.dumps({'mid': mid, 'ruleid': None}))


def await_mail(to_call_on, queue_name=None):
    if queue_name is None:
        queue_name = 'write-to-search'
    q = sqs.get_queue(queue_name)

    backoff = 0
    while True:
        msgs = q.get_messages(visibility_timeout=15, wait_time_seconds=3)
        if len(msgs) == 0:
            if backoff == 0:
                backoff = 1
            print "backing off"
            time.sleep(backoff)
            backoff *= 2
            continue
        backoff = 0
        msg = msgs[0]
        print "Received message: ", msg.get_body_encoded()
        to_call_on(msg.get_body_encoded())
        print "Of type ", type(msg)
        msg.delete()
        exit()
